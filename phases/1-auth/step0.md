# Step 0: auth-backend

## 읽어야 할 파일

먼저 아래 파일들을 읽고 인증 설계를 파악하라:

- `/docs/PRD.md` — 섹션 3 "인증 및 권한" 전체 (로그인 처리, 최초 로그인, 비밀번호 정책, 실패 처리, Admin 계정, 권한 체계)
- `/docs/ARCHITECTURE.md` — "인증 흐름", "에러 응답 형식", "에러 코드 목록"
- `/docs/ADR.md` — ADR-007 (JWT), ADR-008 (bcrypt), ADR-020 (계정 잠금)
- `phases/0-foundation/index.json` — step 0~2 summary 확인
- `backend/app/models/org.py` — Employee, AdminAccount, UsedToken 모델
- `backend/app/models/audit.py` — AuditLog 모델
- `backend/app/config.py` — Settings 필드 (토큰 만료 시간, 잠금 설정 등)
- `backend/app/dependencies.py` — get_current_user 스켈레톤 (이 step에서 완성)

## 작업

### 목표
JWT 기반 인증 시스템을 완성한다. 로그인, 로그아웃, 토큰 갱신, 비밀번호 변경, 계정 잠금, admin 계정 처리를 구현한다.

### `backend/app/services/auth_service.py`

아래 함수 시그니처로 구현한다:

```python
async def login(emp_no: str, password: str, db: AsyncSession, ip: str, ua: str) -> dict:
    """
    반환: {"access_token": str, "token_type": "bearer", "is_initial_password": bool}
    - 퇴직 직원: HTTPException 403 ACCOUNT_DISABLED
    - 잠금 중: HTTPException 423 ACCOUNT_LOCKED (헤더에 unlock_at 포함)
    - 비밀번호 불일치: 실패 횟수 +1, 5회 도달 시 locked_until 설정, HTTPException 401 INVALID_CREDENTIALS
    - 성공: 실패 횟수 초기화, AuditLog LOGIN 기록, AT+RT 발급
    - RT는 HttpOnly SameSite=Strict 쿠키로 응답 헤더에 추가 (반환값 dict에 포함 안 함)
    """

async def admin_login(username: str, password: str, db: AsyncSession, ip: str, ua: str) -> dict:
    """admin 계정 로그인. Employee 테이블 아닌 AdminAccount 테이블 사용"""

async def refresh_access_token(refresh_token: str, db: AsyncSession) -> str:
    """
    - RT의 jti를 UsedToken 테이블에서 확인 → 이미 사용된 경우 HTTPException 401 TOKEN_EXPIRED
    - RT 만료 확인
    - 새 AT 발급 후 jti를 UsedToken에 INSERT (1회 사용 원칙)
    - 반환: 새 access_token 문자열
    """

async def change_password(emp_no: str, current_pw: str, new_pw: str, db: AsyncSession) -> None:
    """
    - current_pw 검증 실패: HTTPException 401 INVALID_CREDENTIALS
    - new_pw 정책 검증: 8자 이상, 영문+숫자 조합, 행번과 동일 불가, 연속 동일 문자 4자 이상 금지
    - 정책 위반: HTTPException 422 INVALID_PASSWORD_POLICY (메시지에 위반 항목 명시)
    - 성공: 비밀번호 업데이트, is_initial_password=False
    """

async def create_access_token(subject: str, is_admin: bool, extra: dict = {}) -> str:
    """JWT AT 생성. exp = now + settings.access_token_expire_minutes"""

async def create_refresh_token(subject: str) -> tuple[str, str]:
    """JWT RT 생성. 반환: (rt_jwt_string, jti). exp = now + settings.refresh_token_expire_days * 86400"""

async def verify_access_token(token: str) -> dict:
    """
    - 만료: HTTPException 401 TOKEN_EXPIRED
    - 서명 오류: HTTPException 401 INVALID_CREDENTIALS
    - 반환: payload dict (sub, is_admin, is_initial_password 등)
    """
```

### `backend/app/dependencies.py` 완성

Phase 0에서 스켈레톤으로 만든 파일을 실제 구현으로 교체한다:

```python
async def get_current_user(token: str | None = Depends(oauth2_scheme), db = Depends(get_db)) -> Employee | AdminAccount:
    """
    - token이 None 또는 검증 실패: HTTPException 401
    - payload의 sub가 'admin'이면 AdminAccount 반환
    - 그 외 emp_no로 Employee 조회. 퇴직이면 403 ACCOUNT_DISABLED
    - Employee.is_initial_password=True이면 별도 플래그 설정 (비밀번호 변경 API 외 403 강제)
    """

async def require_active_user(user = Depends(get_current_user)):
    """is_initial_password=True인 경우 HTTPException 403 FORCE_PASSWORD_CHANGE"""

async def require_admin(user = Depends(require_active_user)):
    """user.is_admin=False이면 HTTPException 403 FORBIDDEN"""

async def require_room_manager(user = Depends(require_active_user)):
    """user.is_room_manager=False이고 is_admin=False이면 HTTPException 403 FORBIDDEN"""
```

### `backend/app/routers/auth.py`

```python
router = APIRouter(prefix="/api/auth", tags=["auth"])

POST /api/auth/login          → login (행번+비밀번호 또는 admin)
POST /api/auth/logout         → RT 쿠키 삭제 (Max-Age=0)
POST /api/auth/token/refresh  → refresh_access_token
POST /api/auth/password/change → change_password (require_active_user 의존성)
POST /api/auth/admin/reset-password → admin 비밀번호 초기화
    # Authorization: Bearer {ADMIN_RESET_TOKEN} 헤더로 인증
    # AdminAccount.password_hash = bcrypt('admin123'), is_initial_password=True
```

### `backend/app/repositories/auth_repo.py`

```python
async def get_employee_by_emp_no(emp_no: str, db: AsyncSession) -> Employee | None
async def get_admin_account(db: AsyncSession) -> AdminAccount | None
async def create_admin_account_if_not_exists(db: AsyncSession) -> None
    """앱 시작 시 한 번 실행. admin 계정 없으면 초기 비밀번호 'admin123'으로 생성"""
async def increment_login_fail(emp_no: str, db: AsyncSession) -> int
    """반환: 현재 실패 횟수"""
async def lock_account(emp_no: str, until: datetime, db: AsyncSession) -> None
async def reset_login_fail(emp_no: str, db: AsyncSession) -> None
async def record_audit(log: AuditLog, db: AsyncSession) -> None
async def is_token_used(jti: str, db: AsyncSession) -> bool
async def mark_token_used(jti: str, expires_at: datetime, db: AsyncSession) -> None
```

### `backend/tests/test_auth.py`

아래 시나리오를 pytest로 작성한다 (DB 픽스처는 트랜잭션 롤백 방식):

- 정상 로그인 → AT/RT 발급, `is_initial_password=True` 확인
- 잘못된 비밀번호 → 401 반환
- 5회 실패 → 계정 잠금, 이후 시도는 423 반환
- 퇴직 직원 로그인 → 403 ACCOUNT_DISABLED
- AT 만료 시뮬레이션 → RT로 갱신 성공
- 동일 RT 두 번 사용 → 두 번째는 401
- 최초 비밀번호 상태에서 비(비밀번호 변경) API 접근 → 403 FORCE_PASSWORD_CHANGE
- 비밀번호 정책 위반 (8자 미만, 숫자 없음, 행번 동일) → 422

### `backend/app/main.py` 수정

auth 라우터를 등록하고, 앱 시작 시 admin 계정 초기화 함수를 `startup` 이벤트에 추가한다:

```python
from app.routers import auth
app.include_router(auth.router)

@app.on_event("startup")
async def startup_event():
    async for db in get_db():
        await auth_repo.create_admin_account_if_not_exists(db)
        break
```

## Acceptance Criteria

```bash
cd backend

# 테스트 실행
uv run pytest tests/test_auth.py -v

# 린트
uv run ruff check app/routers/auth.py app/services/auth_service.py app/repositories/auth_repo.py app/dependencies.py

# 수동 확인: 서버 구동 후 로그인 API 호출
uv run uvicorn app.main:app --port 8001 &
sleep 2
curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python3 -m json.tool
kill %1
```

## 검증 절차

1. `uv run pytest tests/test_auth.py -v` 전체 통과 확인
2. 체크리스트:
   - bcrypt cost factor가 12로 설정되어 있는가?
   - AT는 응답 body에, RT는 HttpOnly SameSite=Strict 쿠키에만 있는가?
   - 로그인 실패 응답에서 "행번이 존재하지 않습니다" 같은 존재 여부 힌트가 없는가?
   - 잠금 응답(423)에 `X-Unlock-At` 헤더가 있는가?
   - 감사 로그(AuditLog)에 LOGIN, LOGIN_FAIL이 기록되는가?
3. `phases/1-auth/index.json` step 0 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "JWT 인증 완성: 로그인/로그아웃/AT갱신/비밀번호변경/계정잠금(5회→30분)/admin별도계정/초기비밀번호강제변경. AuditLog 연동. 테스트 N개 통과"`
   - 실패 3회 → `"status": "error"`, `"error_message": "구체적 에러"`

## 금지사항

- `SECRET_KEY`를 코드에 하드코드 금지. 이유: `settings.secret_key`에서 읽어야 함
- RT를 응답 body에 포함 금지. 이유: XSS 탈취 방지를 위해 HttpOnly 쿠키에만
- 로그인 실패 시 행번 존재 여부를 다른 에러 코드로 구분 금지. 이유: 계정 열거 공격 방지
- `passlib.hash.bcrypt.using(rounds=4)` 등 cost factor 낮추기 금지 (테스트 속도 목적이라도). 이유: 보안 취약. 테스트에서는 mock/fixture 활용
