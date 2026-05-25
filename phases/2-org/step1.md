# Step 1: etl-sync

## 읽어야 할 파일

먼저 아래 파일들을 읽고 ETL 동기화 설계를 파악하라:

- `/docs/PRD.md` — 섹션 2 "직원원장 동기화 (ETL)" 전체 (임시원장, 배치 동기화 규칙, 엣지 케이스, 개발 환경 Mock)
- `/docs/ARCHITECTURE.md` — "ETL 동기화 흐름", "배치 스케줄러 (APScheduler)"
- `/docs/ADR.md` — ADR-012 (ETL 동기화), ADR-015 (APScheduler)
- `phases/2-org/index.json` — step 0 summary
- `backend/app/models/org.py` — EmployeeStaging, Employee, EmployeeHistory
- `backend/app/repositories/org_repo.py` — 직원 관련 함수

## 작업

### 목표
ETL 임시원장 → 직원원장 동기화 배치를 구현한다. APScheduler로 매일 새벽 자동 실행하고, admin API로 수동 실행도 지원한다.

### `backend/app/repositories/staging_repo.py`

```python
async def get_all_staging(db: AsyncSession) -> list[EmployeeStaging]
async def count_staging(db: AsyncSession) -> int
async def truncate_staging(db: AsyncSession) -> None
async def upsert_staging(records: list[dict], db: AsyncSession) -> None
    # Mock 용: Admin UI에서 스테이징 직접 편집
async def get_staging_record(emp_no: str, db: AsyncSession) -> EmployeeStaging | None
async def delete_staging_record(emp_no: str, db: AsyncSession) -> None
```

### `backend/app/services/sync_service.py`

```python
async def run(db: AsyncSession, triggered_by: str = "scheduler") -> dict:
    """
    반환: {"added": int, "updated": int, "retired": int, "skipped": int}

    실행 순서:
    1. staging 건수 확인 → 0이면 AuditLog BATCH_RUN(경고) 기록 후 즉시 반환
    2. 전체 staging 조회 (emp_no 기준 dict 변환)
    3. 전체 employee 조회 (emp_no 기준 dict 변환)
    4. 분류:
       - staging에만 있음: 신규 (INSERT)
       - 양쪽 있고 내용 다름: 변경 (UPDATE, 비밀번호·권한·로그인관련 필드 제외)
       - 양쪽 있고 내용 같음: 스킵
       - employee에만 있음, status=ACTIVE: 퇴직 처리 (status=RETIRED)
       - employee에만 있음, status=RETIRED: 이미 퇴직 → 스킵
    5. 트랜잭션 내에서 Employee CRUD + EmployeeHistory 기록 일괄 처리
    6. staging TRUNCATE
    7. AuditLog BATCH_RUN 기록 (결과 통계 포함)
    """
```

**엣지 케이스 처리 (반드시 구현):**
- 이미 퇴직 처리된 직원이 스테이징에 재등장 → `status=ACTIVE`로 복원, `is_initial_password=True`, `password_hash=bcrypt(emp_no)` 초기화
- 배치 실행 중 예외 → 전체 트랜잭션 롤백, AuditLog에 에러 detail 기록

### `backend/app/scheduler.py`

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import settings

scheduler = AsyncIOScheduler(timezone="Asia/Seoul")

def setup_scheduler(app):
    """FastAPI startup 이벤트에서 호출"""
    @scheduler.scheduled_job("cron", **_parse_cron(settings.sync_cron))
    async def sync_job():
        async for db in get_db():
            await sync_service.run(db, triggered_by="scheduler")
            break

    scheduler.start()

def shutdown_scheduler():
    """FastAPI shutdown 이벤트에서 호출"""
    scheduler.shutdown()

def _parse_cron(cron_str: str) -> dict:
    # "0 2 * * *" → {"minute": 0, "hour": 2, ...}
```

### `backend/app/routers/admin.py` (부분 구현)

이 step에서는 admin 라우터의 ETL 관련 엔드포인트만 구현한다:

```python
router = APIRouter(prefix="/api/admin", tags=["admin"])

# ETL 동기화 관련
POST   /api/admin/sync/run    → sync_service.run() 즉시 실행 (require_admin)
    응답: {"added": N, "updated": N, "retired": N, "skipped": N, "triggered_by": "admin"}

# 개발 환경 Mock (임시원장 직접 조작)
GET    /api/admin/staging     → 전체 스테이징 목록
POST   /api/admin/staging     → 스테이징 레코드 추가/수정 (upsert)
DELETE /api/admin/staging/{emp_no} → 스테이징 레코드 삭제
```

### `backend/tests/test_sync.py`

아래 시나리오를 테스트한다:

- 신규 직원 동기화 → Employee INSERT, is_initial_password=True, 초기 비밀번호=행번
- 정보 변경 동기화 → UPDATE (비밀번호·권한 필드는 유지)
- 내용 동일 → 아무 변경 없음
- 퇴직 처리 → status=RETIRED, EmployeeHistory(DELETE) 기록
- 스테이징 비어있을 때 → 실행 중단, 직원 퇴직 처리 없음
- 이미 퇴직한 직원이 스테이징에 재등장 → 재직 복원, 비밀번호 초기화

### `backend/app/main.py` 수정

scheduler 등록 및 admin 라우터 추가:
```python
app.include_router(admin.router)

@app.on_event("startup")
async def startup_event():
    setup_scheduler(app)

@app.on_event("shutdown")
async def shutdown_event():
    shutdown_scheduler()
```

## Acceptance Criteria

```bash
cd backend
uv run pytest tests/test_sync.py -v
uv run ruff check app/services/sync_service.py app/scheduler.py app/repositories/staging_repo.py
```

## 검증 절차

1. 테스트 전체 통과 확인
2. 체크리스트:
   - 비밀번호·권한 필드(`password_hash`, `is_admin`, `is_room_manager`, `login_fail_count`)가 동기화로 덮어씌워지지 않는가?
   - 스테이징이 0건일 때 전원 퇴직 처리가 발생하지 않는가?
   - 배치 실패 시 전체 롤백이 되는가? (중간 상태가 DB에 남지 않는가?)
   - `POST /api/admin/sync/run`이 admin 권한 없이 호출되면 403이 반환되는가?
3. `phases/2-org/index.json` step 1 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "ETL 동기화 배치 완성: sync_service(신규/변경/퇴직/복원 처리)/APScheduler(KST cron)/admin 수동실행 API/Mock 스테이징 API. 안전장치(빈스테이징 중단) 포함"`

## 금지사항

- 동기화 로직에서 `password_hash`, `is_admin`, `is_room_manager`, `login_fail_count`, `locked_until`, `is_initial_password` 필드를 스테이징 데이터로 덮어쓰기 금지. 이유: ETL은 인사정보만 동기화, 보안/권한 정보는 시스템이 관리
- `staging TRUNCATE`를 트랜잭션 커밋 이전에 수행 금지. 이유: 롤백 시 스테이징 데이터도 복원되어야 함
- 개발 환경 Mock API(`/admin/staging`)를 `APP_ENV` 조건 없이 등록 금지. 이유: 운영 환경에서 임시원장 직접 편집 불가
