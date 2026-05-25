# Step 1: file-backend

## 읽어야 할 파일

먼저 아래 파일들을 읽고 파일 업로드 설계를 파악하라:

- `/docs/PRD.md` — 섹션 6 "파일 첨부" 전체 (허용 확장자, 크기 제한, 저장 경로, 삭제 규칙)
- `/docs/ARCHITECTURE.md` — "데이터 흐름: 파일 업로드", "API 엔드포인트 목록" (파일 섹션)
- `/docs/ADR.md` — ADR-011 (로컬 파일시스템), ADR-023 (XHR 업로드)
- `phases/4-meeting/index.json` — step 0 summary
- `backend/app/models/room.py` — MeetingFile 모델
- `backend/app/config.py` — settings (UPLOAD_DIR, MAX_FILE_SIZE 등)

## 작업

### 목표
회의 첨부파일 업로드/다운로드/삭제 API를 구현한다. 파일은 로컬 파일시스템에 저장하고, DB에는 메타데이터만 기록한다.

### `backend/app/repositories/file_repo.py`

```python
async def get_files(meeting_id: str, db) -> list[MeetingFile]
async def get_file(file_id: str, db) -> MeetingFile | None
async def create_file(meeting_id: str, data: dict, db) -> MeetingFile
    # data: {original_name, stored_name, file_path, mime_type, size, uploaded_by}
async def delete_file(file_id: str, db) -> None
    # DB 레코드만 삭제 (물리 파일 삭제는 라우터에서)
```

### `backend/app/routers/files.py`

```python
router = APIRouter(prefix="/api/meetings", tags=["files"])

POST   /api/meetings/{meeting_id}/files
    """
    - require_active_user
    - SCHEDULED 상태 회의에만 파일 추가 가능 → 아니면 422
    - 요청자가 해당 회의 참석자 또는 주최자인지 확인 → 아니면 403
    - Content-Type: multipart/form-data, 필드명: file
    - 허용 확장자: pdf, doc, docx, xls, xlsx, ppt, pptx, jpg, jpeg, png, gif, zip
      → 아니면 415 UNSUPPORTED_MEDIA_TYPE
    - 파일 크기 제한: settings.MAX_FILE_SIZE (기본 50MB)
      → 초과 시 413 FILE_TOO_LARGE
    - 저장 경로: {settings.UPLOAD_DIR}/{meeting_id}/{uuid4()}_{original_filename}
    - DB INSERT (MeetingFile)
    - 응답: MeetingFileResponse
    """

GET    /api/meetings/{meeting_id}/files
    # require_active_user, 파일 목록 반환

GET    /api/meetings/{meeting_id}/files/{file_id}
    """
    - require_active_user
    - FileResponse(path, media_type, filename=original_name)
    - Content-Disposition: attachment; filename="{original_name}"
    """

DELETE /api/meetings/{meeting_id}/files/{file_id}
    """
    - require_active_user
    - 업로드한 본인 또는 is_admin만 삭제 가능 → 아니면 403
    - SCHEDULED 상태 회의에만 삭제 가능 → 아니면 422
    - 물리 파일 삭제 (os.remove) 후 DB 레코드 삭제
    - 물리 파일 없어도 DB는 정상 삭제 (best-effort)
    """
```

### `backend/app/schemas/meeting.py` 추가

기존 meeting.py에 추가:

```python
class MeetingFileResponse(BaseModel):
    id: str
    original_name: str
    mime_type: str
    size: int           # bytes
    uploaded_by: str
    uploaded_by_name: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

### `backend/app/config.py` 확인/추가

```python
upload_dir: str = "/app/uploads"
max_file_size: int = 52428800  # 50MB in bytes
allowed_extensions: set[str] = {"pdf","doc","docx","xls","xlsx","ppt","pptx","jpg","jpeg","png","gif","zip"}
```

### `backend/app/main.py` 수정

```python
# UPLOAD_DIR 마운트 (정적 파일이 아닌 API를 통해서만 접근 가능 — StaticFiles 마운트 금지)
app.include_router(files.router)

# 서버 시작 시 UPLOAD_DIR 없으면 생성
@app.on_event("startup")
async def startup_event():
    os.makedirs(settings.upload_dir, exist_ok=True)
    ...
```

### `backend/tests/test_files.py`

아래 시나리오를 테스트한다:

- PDF 파일 업로드 → DB 레코드 생성, 파일시스템에 저장
- 허용되지 않는 확장자(.exe) 업로드 → 415
- 50MB 초과 파일 업로드 → 413
- 파일 다운로드 → Content-Disposition 헤더 포함
- 업로드한 본인이 아닌 사용자 삭제 → 403
- admin이 남의 파일 삭제 → 성공
- CANCELLED 회의에 파일 업로드 → 422
- 파일 삭제 시 물리 파일도 삭제되는지 확인 (os.path.exists)
- 참석자가 아닌 사용자의 파일 업로드 → 403

## Acceptance Criteria

```bash
cd backend
uv run pytest tests/test_files.py -v
uv run ruff check app/routers/files.py app/repositories/file_repo.py
```

## 검증 절차

1. 테스트 전체 통과 확인
2. 체크리스트:
   - 업로드 파일이 `{UPLOAD_DIR}/{meeting_id}/` 하위에 `{uuid}_{original_name}` 형식으로 저장되는가?
   - `/api/meetings/{id}/files/{file_id}` 직접 URL로 접근 시 API 인증을 거치는가? (StaticFiles 마운트 금지 확인)
   - 파일 삭제 시 물리 파일이 없어도 DB 삭제는 성공하는가? (best-effort)
   - 확장자 검사가 Content-Type이 아닌 파일명 기준으로 동작하는가?
3. `phases/4-meeting/index.json` step 1 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "파일 업로드/다운로드/삭제 API 완성. 확장자/크기 검증, UUID 저장경로, 참석자 권한 확인, 물리파일+DB 동시삭제(best-effort)"`

## 금지사항

- `/app/uploads` 를 FastAPI StaticFiles 또는 nginx로 직접 노출 금지. 이유: 인증 없이 파일 접근 가능해짐
- 파일을 DB에 binary blob으로 저장 금지. 이유: ADR-011 로컬 파일시스템 저장 결정
- 확장자 검사를 Content-Type 헤더만으로 하지 마라. 이유: 클라이언트가 조작 가능
- `pip install` 금지. 이유: uv 사용 프로젝트
