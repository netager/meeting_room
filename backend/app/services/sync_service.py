from __future__ import annotations

import json

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Employee, EmployeeHistory, EmployeeStaging
from app.repositories import staging_repo

logger = structlog.get_logger(__name__)

# Fields that must never be overwritten by ETL sync
_PROTECTED = frozenset(
    {"password_hash", "is_admin", "is_room_manager", "login_fail_count", "locked_until", "is_initial_password"}
)

# Fields to compare for change detection (subset of ETL-managed fields)
_SYNC_FIELDS = ("name", "dept_code", "team_code", "rank")


def _staging_to_dict(s: EmployeeStaging) -> dict:
    return {
        "emp_no": s.emp_no,
        "name": s.name,
        "dept_code": s.dept_code,
        "team_code": s.team_code,
        "rank": s.rank,
    }


def _emp_to_sync_dict(e: Employee) -> dict:
    return {
        "emp_no": e.emp_no,
        "name": e.name,
        "dept_code": e.dept_code,
        "team_code": e.team_code,
        "rank": e.rank,
    }


def _emp_to_full_dict(e: Employee) -> dict:
    return {
        "emp_no": e.emp_no,
        "name": e.name,
        "dept_code": e.dept_code,
        "team_code": e.team_code,
        "rank": e.rank,
        "status": e.status,
        "is_admin": e.is_admin,
        "is_room_manager": e.is_room_manager,
    }


async def _log_audit(
    actor: str,
    detail: str,
    db: AsyncSession,
) -> None:
    try:
        from app.db import AsyncSessionLocal

        async with AsyncSessionLocal() as audit_db:
            log = AuditLog(
                actor=actor,
                action="BATCH_RUN",
                target_table="employee",
                detail=detail,
            )
            audit_db.add(log)
            await audit_db.commit()
    except Exception:
        pass  # best-effort


async def run(db: AsyncSession, triggered_by: str = "scheduler") -> dict:
    """
    ETL 임시원장 → 직원원장 동기화.

    Returns {"added": int, "updated": int, "retired": int, "skipped": int}
    """
    # 1. staging 건수 확인
    staging_count = await staging_repo.count_staging(db)
    if staging_count == 0:
        detail = json.dumps(
            {"warning": "staging empty — sync aborted to prevent mass retirement", "triggered_by": triggered_by},
            ensure_ascii=False,
        )
        await _log_audit(triggered_by, detail, db)
        logger.warning("sync_aborted", reason="staging_empty", triggered_by=triggered_by)
        return {"added": 0, "updated": 0, "retired": 0, "skipped": 0}

    # 2. 전체 staging 조회
    staging_list = await staging_repo.get_all_staging(db)
    staging_map: dict[str, EmployeeStaging] = {s.emp_no: s for s in staging_list}

    # 3. 전체 employee 조회 (페이지네이션 없이 전체)
    from sqlalchemy import select

    result = await db.execute(select(Employee))
    all_employees = list(result.scalars().all())
    employee_map: dict[str, Employee] = {e.emp_no: e for e in all_employees}

    added = 0
    updated = 0
    retired = 0
    skipped = 0

    try:
        # 4. 분류 및 처리
        for emp_no, staging in staging_map.items():
            if emp_no in employee_map:
                emp = employee_map[emp_no]

                if emp.status == "RETIRED":
                    # 이미 퇴직한 직원 재등장 → 재직 복원, 비밀번호 초기화
                    before = _emp_to_full_dict(emp)
                    emp.status = "ACTIVE"
                    emp.name = staging.name
                    emp.dept_code = staging.dept_code
                    emp.team_code = staging.team_code
                    emp.rank = staging.rank
                    emp.is_initial_password = True

                    from app.services.auth_service import hash_password
                    emp.password_hash = hash_password(emp_no)

                    await db.flush()
                    history = EmployeeHistory(
                        target_id=emp_no,
                        change_type="UPDATE",
                        before_data=before,
                        after_data=_emp_to_full_dict(emp),
                        changed_by=triggered_by,
                    )
                    db.add(history)
                    added += 1  # 복원도 신규와 동일하게 처리
                    continue

                # 내용 비교 (sync 필드만)
                staging_vals = {f: getattr(staging, f) for f in _SYNC_FIELDS}
                emp_vals = {f: getattr(emp, f) for f in _SYNC_FIELDS}

                if staging_vals == emp_vals:
                    skipped += 1
                else:
                    before = _emp_to_full_dict(emp)
                    for field in _SYNC_FIELDS:
                        setattr(emp, field, getattr(staging, field))
                    await db.flush()
                    history = EmployeeHistory(
                        target_id=emp_no,
                        change_type="UPDATE",
                        before_data=before,
                        after_data=_emp_to_full_dict(emp),
                        changed_by=triggered_by,
                    )
                    db.add(history)
                    updated += 1
            else:
                # 신규 직원
                from app.services.auth_service import hash_password

                emp = Employee(
                    emp_no=emp_no,
                    name=staging.name,
                    dept_code=staging.dept_code,
                    team_code=staging.team_code,
                    rank=staging.rank,
                    status="ACTIVE",
                    password_hash=hash_password(emp_no),
                    is_admin=False,
                    is_room_manager=False,
                    is_initial_password=True,
                    login_fail_count=0,
                )
                db.add(emp)
                await db.flush()
                history = EmployeeHistory(
                    target_id=emp_no,
                    change_type="CREATE",
                    before_data=None,
                    after_data=_emp_to_full_dict(emp),
                    changed_by=triggered_by,
                )
                db.add(history)
                added += 1

        # employee에만 있고 ACTIVE인 직원 → 퇴직 처리
        for emp_no, emp in employee_map.items():
            if emp_no not in staging_map and emp.status == "ACTIVE":
                before = _emp_to_full_dict(emp)
                emp.status = "RETIRED"
                await db.flush()
                history = EmployeeHistory(
                    target_id=emp_no,
                    change_type="DELETE",
                    before_data=before,
                    after_data=_emp_to_full_dict(emp),
                    changed_by=triggered_by,
                )
                db.add(history)
                retired += 1

        # 5. staging TRUNCATE (트랜잭션 내, 커밋 전)
        from sqlalchemy import text
        await db.execute(text("TRUNCATE TABLE employee_staging"))

        # 6. 트랜잭션 커밋
        await db.commit()

    except Exception as exc:
        await db.rollback()
        err_detail = json.dumps(
            {"error": str(exc), "triggered_by": triggered_by}, ensure_ascii=False
        )
        await _log_audit(triggered_by, err_detail, db)
        logger.error("sync_failed", exc_info=exc, triggered_by=triggered_by)
        raise

    # 7. AuditLog 기록
    result_detail = json.dumps(
        {
            "added": added,
            "updated": updated,
            "retired": retired,
            "skipped": skipped,
            "triggered_by": triggered_by,
        },
        ensure_ascii=False,
    )
    await _log_audit(triggered_by, result_detail, db)
    logger.info(
        "sync_completed",
        added=added,
        updated=updated,
        retired=retired,
        skipped=skipped,
        triggered_by=triggered_by,
    )

    return {"added": added, "updated": updated, "retired": retired, "skipped": skipped}
