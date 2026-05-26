"""
File upload/download/delete API tests.

Covers:
- PDF 파일 업로드 → DB 레코드 생성, 파일시스템에 저장
- 허용되지 않는 확장자(.exe) 업로드 → 415
- 50MB 초과 파일 업로드 → 413
- 파일 다운로드 → Content-Disposition 헤더 포함
- 업로드한 본인이 아닌 사용자 삭제 → 403
- admin이 남의 파일 삭제 → 성공
- CANCELLED 회의에 파일 업로드 → 422
- 파일 삭제 시 물리 파일도 삭제되는지 확인 (os.path.exists)
- 참석자가 아닌 사용자의 파일 업로드 → 403
"""

from __future__ import annotations

import datetime
import io
import os

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AdminAccount, Employee
from app.models.meeting import Meeting, MeetingAttendee
from app.models.room import MeetingRoom


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_token(sub: str, is_admin: bool = False) -> str:
    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    payload = {
        "sub": sub,
        "is_admin": is_admin,
        "exp": now + datetime.timedelta(minutes=30),
        "iat": now,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def _emp_headers(emp: Employee) -> dict:
    return {"Authorization": f"Bearer {_make_token(emp.emp_no)}"}


def _admin_headers(admin: AdminAccount) -> dict:
    return {"Authorization": f"Bearer {_make_token('admin', is_admin=True)}"}


def _pdf_file(name: str = "report.pdf", size: int = 1024) -> tuple[str, tuple]:
    content = b"PDF content " * (size // 12 + 1)
    return ("file", (name, io.BytesIO(content[:size]), "application/pdf"))


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def room(db: AsyncSession) -> MeetingRoom:
    r = MeetingRoom(
        name="파일테스트회의실",
        location="본관 1층",
        status="NORMAL",
        dept_code="TESTDEPT",
    )
    db.add(r)
    await db.flush()
    return r


@pytest.fixture
async def uploader(db: AsyncSession) -> Employee:
    emp = Employee(
        emp_no="F00001",
        name="업로더",
        dept_code="TESTDEPT",
        password_hash="$test$Password1",
        status="ACTIVE",
        is_initial_password=False,
        login_fail_count=0,
    )
    db.add(emp)
    await db.flush()
    return emp


@pytest.fixture
async def other_emp(db: AsyncSession) -> Employee:
    emp = Employee(
        emp_no="F00002",
        name="다른직원",
        dept_code="TESTDEPT",
        password_hash="$test$Password1",
        status="ACTIVE",
        is_initial_password=False,
        login_fail_count=0,
    )
    db.add(emp)
    await db.flush()
    return emp


@pytest.fixture
async def scheduled_meeting(
    db: AsyncSession, room: MeetingRoom, uploader: Employee
) -> Meeting:
    meeting = Meeting(
        title="파일업로드회의",
        date=datetime.date.today() + datetime.timedelta(days=1),
        start_time=datetime.time(10, 0),
        end_time=datetime.time(11, 0),
        room_id=room.id,
        status="SCHEDULED",
        dept_code="TESTDEPT",
        created_by=uploader.emp_no,
    )
    db.add(meeting)
    await db.flush()
    db.add(MeetingAttendee(meeting_id=meeting.id, emp_no=uploader.emp_no))
    await db.flush()
    return meeting


@pytest.fixture
async def cancelled_meeting(
    db: AsyncSession, room: MeetingRoom, uploader: Employee
) -> Meeting:
    meeting = Meeting(
        title="취소된회의",
        date=datetime.date.today() + datetime.timedelta(days=2),
        start_time=datetime.time(14, 0),
        end_time=datetime.time(15, 0),
        room_id=room.id,
        status="CANCELLED",
        dept_code="TESTDEPT",
        created_by=uploader.emp_no,
    )
    db.add(meeting)
    await db.flush()
    db.add(MeetingAttendee(meeting_id=meeting.id, emp_no=uploader.emp_no))
    await db.flush()
    return meeting


# ── Tests ─────────────────────────────────────────────────────────────────────


async def test_upload_pdf_creates_db_record_and_file(
    client: AsyncClient,
    db: AsyncSession,
    uploader: Employee,
    scheduled_meeting: Meeting,
    tmp_path,
    monkeypatch,
):
    """PDF 파일 업로드 → DB 레코드 생성, 파일시스템에 저장."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    resp = await client.post(
        f"/api/meetings/{scheduled_meeting.id}/files",
        files=[_pdf_file("보고서.pdf")],
        headers=_emp_headers(uploader),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["original_name"] == "보고서.pdf"
    assert data["uploaded_by"] == uploader.emp_no

    # 파일시스템에 저장 확인
    meeting_dir = tmp_path / scheduled_meeting.id
    files_on_disk = list(meeting_dir.iterdir())
    assert len(files_on_disk) == 1
    assert files_on_disk[0].name.endswith("보고서.pdf")


async def test_upload_disallowed_extension_returns_415(
    client: AsyncClient,
    uploader: Employee,
    scheduled_meeting: Meeting,
    tmp_path,
    monkeypatch,
):
    """허용되지 않는 확장자(.exe) 업로드 → 415."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    resp = await client.post(
        f"/api/meetings/{scheduled_meeting.id}/files",
        files=[("file", ("malware.exe", io.BytesIO(b"evil"), "application/octet-stream"))],
        headers=_emp_headers(uploader),
    )
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


async def test_upload_oversized_file_returns_413(
    client: AsyncClient,
    uploader: Employee,
    scheduled_meeting: Meeting,
    tmp_path,
    monkeypatch,
):
    """50MB 초과 파일 업로드 → 413."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "max_file_size", 10)  # 10 bytes limit

    resp = await client.post(
        f"/api/meetings/{scheduled_meeting.id}/files",
        files=[("file", ("big.pdf", io.BytesIO(b"X" * 100), "application/pdf"))],
        headers=_emp_headers(uploader),
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"


async def test_download_file_has_content_disposition(
    client: AsyncClient,
    uploader: Employee,
    scheduled_meeting: Meeting,
    tmp_path,
    monkeypatch,
):
    """파일 다운로드 → Content-Disposition: attachment 헤더 포함."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    # 먼저 업로드
    upload_resp = await client.post(
        f"/api/meetings/{scheduled_meeting.id}/files",
        files=[_pdf_file("발표자료.pdf")],
        headers=_emp_headers(uploader),
    )
    assert upload_resp.status_code == 201
    file_id = upload_resp.json()["id"]

    # 다운로드
    dl_resp = await client.get(
        f"/api/meetings/{scheduled_meeting.id}/files/{file_id}",
        headers=_emp_headers(uploader),
    )
    assert dl_resp.status_code == 200
    content_disposition = dl_resp.headers.get("content-disposition", "")
    assert "attachment" in content_disposition
    # filename* uses RFC 5987 percent-encoding for non-ASCII characters
    import urllib.parse
    assert urllib.parse.quote("발표자료.pdf", safe="") in content_disposition


async def test_delete_by_non_uploader_returns_403(
    client: AsyncClient,
    uploader: Employee,
    other_emp: Employee,
    scheduled_meeting: Meeting,
    tmp_path,
    monkeypatch,
):
    """업로드한 본인이 아닌 사용자 삭제 → 403."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    # other_emp를 참석자로 추가
    db_session = None
    from sqlalchemy import select
    from app.db import get_db
    from app.main import app

    # 참석자로 other_emp 추가 (직접 DB 조작)
    # client 요청으로 참석자 추가
    add_resp = await client.post(
        f"/api/meetings/{scheduled_meeting.id}/attendees",
        json={"emp_no": other_emp.emp_no},
        headers=_emp_headers(uploader),
    )
    assert add_resp.status_code == 201

    # uploader가 업로드
    upload_resp = await client.post(
        f"/api/meetings/{scheduled_meeting.id}/files",
        files=[_pdf_file("비밀문서.pdf")],
        headers=_emp_headers(uploader),
    )
    assert upload_resp.status_code == 201
    file_id = upload_resp.json()["id"]

    # other_emp가 삭제 시도 → 403
    del_resp = await client.delete(
        f"/api/meetings/{scheduled_meeting.id}/files/{file_id}",
        headers=_emp_headers(other_emp),
    )
    assert del_resp.status_code == 403
    assert del_resp.json()["error"]["code"] == "FORBIDDEN"


async def test_admin_can_delete_others_file(
    client: AsyncClient,
    test_admin: AdminAccount,
    uploader: Employee,
    scheduled_meeting: Meeting,
    tmp_path,
    monkeypatch,
):
    """admin이 남의 파일 삭제 → 성공."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    upload_resp = await client.post(
        f"/api/meetings/{scheduled_meeting.id}/files",
        files=[_pdf_file("admin삭제대상.pdf")],
        headers=_emp_headers(uploader),
    )
    assert upload_resp.status_code == 201
    file_id = upload_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/meetings/{scheduled_meeting.id}/files/{file_id}",
        headers=_admin_headers(test_admin),
    )
    assert del_resp.status_code == 200


async def test_upload_to_cancelled_meeting_returns_422(
    client: AsyncClient,
    uploader: Employee,
    cancelled_meeting: Meeting,
    tmp_path,
    monkeypatch,
):
    """CANCELLED 회의에 파일 업로드 → 422."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    resp = await client.post(
        f"/api/meetings/{cancelled_meeting.id}/files",
        files=[_pdf_file("취소회의파일.pdf")],
        headers=_emp_headers(uploader),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "MEETING_ALREADY_CLOSED"


async def test_delete_removes_physical_file(
    client: AsyncClient,
    uploader: Employee,
    scheduled_meeting: Meeting,
    tmp_path,
    monkeypatch,
):
    """파일 삭제 시 물리 파일도 삭제되는지 확인."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    upload_resp = await client.post(
        f"/api/meetings/{scheduled_meeting.id}/files",
        files=[_pdf_file("삭제될파일.pdf")],
        headers=_emp_headers(uploader),
    )
    assert upload_resp.status_code == 201
    file_id = upload_resp.json()["id"]

    # 파일이 디스크에 존재하는지 확인
    meeting_dir = tmp_path / scheduled_meeting.id
    files_before = list(meeting_dir.iterdir())
    assert len(files_before) == 1

    del_resp = await client.delete(
        f"/api/meetings/{scheduled_meeting.id}/files/{file_id}",
        headers=_emp_headers(uploader),
    )
    assert del_resp.status_code == 200

    files_after = list(meeting_dir.iterdir())
    assert len(files_after) == 0, "물리 파일이 삭제되어야 합니다"


async def test_upload_by_non_attendee_returns_403(
    client: AsyncClient,
    other_emp: Employee,
    scheduled_meeting: Meeting,
    tmp_path,
    monkeypatch,
):
    """참석자가 아닌 사용자의 파일 업로드 → 403."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    resp = await client.post(
        f"/api/meetings/{scheduled_meeting.id}/files",
        files=[_pdf_file("비참석자업로드.pdf")],
        headers=_emp_headers(other_emp),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


async def test_delete_missing_physical_file_still_deletes_db(
    client: AsyncClient,
    uploader: Employee,
    scheduled_meeting: Meeting,
    tmp_path,
    monkeypatch,
):
    """물리 파일이 없어도 DB 삭제는 성공 (best-effort)."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))

    upload_resp = await client.post(
        f"/api/meetings/{scheduled_meeting.id}/files",
        files=[_pdf_file("사라진파일.pdf")],
        headers=_emp_headers(uploader),
    )
    assert upload_resp.status_code == 201
    file_id = upload_resp.json()["id"]

    # 물리 파일을 미리 삭제
    meeting_dir = tmp_path / scheduled_meeting.id
    for f in meeting_dir.iterdir():
        f.unlink()

    # DB 삭제 요청 → 성공해야 함
    del_resp = await client.delete(
        f"/api/meetings/{scheduled_meeting.id}/files/{file_id}",
        headers=_emp_headers(uploader),
    )
    assert del_resp.status_code == 200

    # 파일 목록에서도 사라짐
    list_resp = await client.get(
        f"/api/meetings/{scheduled_meeting.id}/files",
        headers=_emp_headers(uploader),
    )
    assert list_resp.status_code == 200
    assert all(f["id"] != file_id for f in list_resp.json())
