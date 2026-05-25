# Step 2: core-infra

## 읽어야 할 파일

먼저 아래 파일들을 읽고 인프라 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md` — "환경 변수", "DB 연결 풀 설정", "애플리케이션 로깅", "보안", "헬스체크", "에러 응답 형식", "CORS 설정"
- `/docs/ADR.md` — ADR-006 (REST), ADR-007 (JWT 개요), ADR-017 (structlog), ADR-018 (KST 타임존)
- `/CLAUDE.md` — 환경 변수 목록
- `phases/0-foundation/index.json` — step 0, 1 summary 확인
- `backend/app/models/` — step 1에서 생성된 모든 모델 파일

## 작업

### 목표
비즈니스 로직 없이 애플리케이션의 핵심 인프라를 구성한다: 환경 변수, DB 연결, 의존성 주입 스켈레톤, 미들웨어, `main.py` 기본 구성.

### `backend/app/config.py`

`pydantic-settings`의 `BaseSettings`를 상속한 `Settings` 클래스를 정의한다:

```python
class Settings(BaseSettings):
    database_url: str
    secret_key: str
    frontend_origin: str
    app_env: str = "development"
    internal_msg_api_url: str = ""
    internal_msg_api_timeout: int = 5
    upload_dir: str = "/app/uploads"
    max_upload_size_mb: int = 50
    admin_reset_token: str = ""
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    login_max_attempts: int = 5
    login_lock_minutes: int = 30
    sync_cron: str = "0 2 * * *"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()  # 모듈 레벨 싱글턴
```

### `backend/app/db.py`

- `create_async_engine` 으로 엔진 생성 (pool_size, max_overflow, pool_timeout, pool_pre_ping=True, echo는 `app_env=="development"` 시에만 True)
- `async_sessionmaker` 로 `AsyncSessionLocal` 팩토리 생성
- `get_db()` async generator: `AsyncSession`을 yield하고 finally에서 close

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

### `backend/app/dependencies.py`

인증 의존성 스켈레톤을 정의한다. 실제 JWT 검증 로직은 Phase 1에서 구현하고, 지금은 타입 시그니처와 뼈대만 작성한다:

```python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Employee:
    # Phase 1에서 구현. 지금은 NotImplementedError
    raise NotImplementedError

async def require_admin(user: Employee = Depends(get_current_user)) -> Employee:
    raise NotImplementedError

async def require_room_manager(user: Employee = Depends(get_current_user)) -> Employee:
    raise NotImplementedError

async def require_active_user(user: Employee = Depends(get_current_user)) -> Employee:
    raise NotImplementedError
```

### `backend/app/middleware/request_id.py`

모든 요청에 `X-Request-ID` 헤더를 주입하는 미들웨어:
- 요청에 `X-Request-ID` 헤더가 있으면 사용, 없으면 UUID 신규 생성
- 응답 헤더에도 동일한 값 추가
- `contextvars.ContextVar`에 request_id 저장 (로깅에서 참조)

### `backend/app/middleware/audit_middleware.py`

AuditLog 기록 미들웨어 스켈레톤:
- `BaseHTTPMiddleware`를 상속
- 요청 처리 후 `AuditLog`를 별도 DB 세션으로 INSERT (메인 트랜잭션과 분리)
- 이 step에서는 모든 요청에 대해 로그를 남기는 기본 구조만 작성. 행위자 추출 등 세부 로직은 Phase 6에서 완성
- AuditLog INSERT 실패가 원래 응답을 실패시키지 않도록 try/except로 보호

```python
class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        try:
            await self._record_audit(request, response)
        except Exception:
            pass  # best-effort, 감사 로그 실패가 응답을 막지 않음
        return response
```

### `backend/app/logging_config.py`

structlog 설정:
- 개발 환경: `ConsoleRenderer` (컬러 출력)
- 운영 환경: `JSONRenderer`
- 포함 필드: `timestamp`, `level`, `logger`, `request_id` (contextvars에서), `message`

```python
def configure_logging(app_env: str) -> None:
    # structlog.configure() 호출
    ...
```

### `backend/app/main.py`

```python
app = FastAPI(title="회의 및 회의실 관리", version="1.0.0")

# 1. 로깅 설정
configure_logging(settings.app_env)

# 2. 미들웨어 등록 (순서 중요: RequestIdMiddleware → AuditMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(RequestIdMiddleware)

# 3. CORS
app.add_middleware(CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# 4. 보안 헤더 미들웨어 (모든 응답에 추가)
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# 5. 전역 예외 핸들러
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    # 스택 트레이스는 로그에만, 응답에는 INTERNAL_ERROR 코드만
    logger.error("Unhandled exception", exc_info=exc, request_id=get_request_id())
    return JSONResponse(status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "서버 내부 오류가 발생했습니다"}})

# 6. 헬스체크 API
@app.get("/api/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    status = "ok" if db_status == "ok" else "degraded"
    return JSONResponse(
        status_code=200 if status == "ok" else 503,
        content={"status": status, "db": db_status, "timestamp": datetime.now().isoformat()})

# 7. 정적 파일 (Svelte 빌드) — frontend/dist가 없으면 조건부 마운트
if os.path.exists("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")
```

### `backend/.env` 생성 (개발용)

`.env.example`을 복사하여 `backend/.env`를 생성하고 로컬 개발에 필요한 최소값을 채운다 (실제 PostgreSQL 연결 문자열 포함). 이 파일은 `.gitignore` 대상이다.

## Acceptance Criteria

```bash
cd backend

# 환경 변수 로딩 확인
uv run python -c "from app.config import settings; print(settings.app_env)"

# DB 연결 확인 (로컬 PostgreSQL 필요)
uv run python -c "
import asyncio
from app.db import get_db
from sqlalchemy import text
async def test():
    async for db in get_db():
        result = await db.execute(text('SELECT 1'))
        print('DB OK:', result.scalar())
asyncio.run(test())
"

# 앱 구동 확인
uv run uvicorn app.main:app --port 8001 &
sleep 2
curl -s http://localhost:8001/api/health | python3 -m json.tool
kill %1

# 린트
uv run ruff check app/
```

## 검증 절차

1. 위 AC 커맨드를 순서대로 실행한다.
2. 체크리스트:
   - `settings = Settings()` 가 모듈 레벨 싱글턴으로 생성되는가?
   - `pool_pre_ping=True` 가 엔진에 설정되어 있는가?
   - `AuditLog` INSERT가 메인 트랜잭션과 분리된 세션으로 수행되는가?
   - 500 에러 응답에 스택 트레이스가 포함되지 않는가?
   - `/api/health` 응답이 DB 상태에 따라 200/503을 반환하는가?
3. `phases/0-foundation/index.json` step 2 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "core-infra 완성: config/db/dependencies 스켈레톤/미들웨어(RequestId+Audit)/보안헤더/전역예외핸들러/헬스체크. structlog 설정 완료"`
   - 실패 3회 → `"status": "error"`, `"error_message": "구체적 에러"`

## 금지사항

- `dependencies.py`의 `get_current_user`를 실제 구현하지 마라. 이유: Phase 1(auth-backend)에서 구현. 지금 구현하면 JWT 라이브러리 설정과 충돌 가능
- `allow_origins=["*"]` CORS 와일드카드 금지. 이유: `settings.frontend_origin` 환경 변수 사용
- 500 에러 응답에 스택 트레이스, 내부 경로, DB 쿼리 정보 포함 금지. 이유: 보안 정보 노출
- `main.py`에 라우터 등록하지 마라. 이유: 각 Phase에서 해당 도메인 라우터를 등록
