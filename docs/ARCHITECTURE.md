# 아키텍처: 회의 및 회의실 관리

## 디렉토리 구조

```
backend/
├── app/
│   ├── main.py                   # FastAPI 앱, CORS, 전역 예외 핸들러, StaticFiles
│   ├── routers/
│   │   ├── auth.py               # POST /login, POST /logout, POST /token/refresh, POST /password/change
│   │   ├── employees.py          # 직원원장 CRUD
│   │   ├── departments.py        # 부서·팀 CRUD
│   │   ├── meeting_rooms.py      # 회의실·집기 CRUD
│   │   ├── meetings.py           # 회의 채널 CRUD, 파일 업로드/다운로드
│   │   ├── notifications.py      # 참석자 직접 메시지 전송
│   │   ├── admin.py              # 권한 부여, 배치 수동 실행, 임시원장 CRUD(Mock)
│   │   ├── audit.py              # 감사 로그 조회 (admin 전용)
│   │   └── dev.py                # APP_ENV=development 시만 등록: Mock 메시지 조회
│   ├── schemas/                  # Pydantic 요청/응답 스키마 (도메인별 파일)
│   ├── models/                   # SQLAlchemy ORM 모델
│   ├── repositories/             # DB 접근 레이어 (CRUD)
│   ├── services/
│   │   ├── auth_service.py       # JWT 발급·검증, 비밀번호 해싱·검증
│   │   ├── meeting_service.py    # 중복 예약 검사, 파일 처리, 상태 전이 검증
│   │   ├── notification_service.py  # 알림 조건 판단, 발송, 재시도
│   │   └── sync_service.py       # 임시원장 → 직원원장 동기화 배치
│   ├── middleware/
│   │   ├── audit_middleware.py   # 모든 요청/응답 가로채어 AuditLog 기록
│   │   └── request_id.py         # X-Request-ID 헤더 주입
│   ├── scheduler.py              # APScheduler 설정, 배치 잡 등록
│   ├── config.py                 # pydantic-settings 환경 변수
│   ├── db.py                     # AsyncSession 팩토리, 엔진, 커넥션 풀 설정
│   └── dependencies.py           # get_db, get_current_user, require_admin, require_room_manager
├── alembic/
│   ├── env.py
│   └── versions/
├── alembic.ini
├── tests/
│   ├── conftest.py               # DB 픽스처 (트랜잭션 롤백), 테스트 클라이언트
│   ├── test_auth.py              # 로그인, 토큰 갱신, 잠금, 최초 로그인
│   ├── test_meetings.py          # 중복 예약, 상태 전이, 파일 업로드
│   ├── test_notifications.py     # 알림 조건, Mock 발송
│   ├── test_sync.py              # ETL 동기화 시나리오
│   └── test_permissions.py      # 권한 체계 전반
├── uploads/                      # 파일 업로드 저장소 (Docker volume)
├── pyproject.toml
└── uv.lock

frontend/
├── src/
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.js         # fetch 래퍼: 에러 처리, 토큰 갱신, 요청 ID
│   │   │   ├── auth.js
│   │   │   ├── employees.js
│   │   │   ├── departments.js
│   │   │   ├── meetingRooms.js
│   │   │   ├── meetings.js
│   │   │   └── notifications.js
│   │   ├── components/
│   │   │   ├── layout/           # AppShell.svelte, Sidebar.svelte, Header.svelte
│   │   │   ├── meeting/          # MeetingForm.svelte, MeetingCard.svelte, AttendeeSelector.svelte
│   │   │   ├── room/             # RoomList.svelte, EquipmentPanel.svelte
│   │   │   └── common/           # Button.svelte, Input.svelte, Modal.svelte, Table.svelte, Badge.svelte, Pagination.svelte, Toast.svelte
│   │   └── stores/
│   │       ├── auth.js           # currentUser, isAuthenticated, isInitialPassword
│   │       ├── toast.js          # 전역 토스트 알림
│   │       └── meetings.js       # 회의 목록 캐시
│   ├── pages/
│   │   ├── Login.svelte
│   │   ├── PasswordChange.svelte  # 최초 로그인 강제 변경 페이지
│   │   ├── Dashboard.svelte
│   │   ├── MeetingList.svelte
│   │   ├── MeetingDetail.svelte
│   │   ├── MeetingForm.svelte    # 생성·수정 공용
│   │   ├── MeetingRoomList.svelte
│   │   ├── Admin.svelte          # 권한 관리, 감사 로그, 배치 실행
│   │   └── DevMessages.svelte    # APP_ENV=development 전용
│   ├── router.js                 # 해시 기반 SPA 라우터 (svelte-routing 또는 직접 구현)
│   ├── app.css
│   └── main.js
├── index.html
├── vite.config.js
└── package.json

docker/
├── Dockerfile                    # 멀티스테이지: Svelte 빌드 + Python 앱
├── docker-compose.yml            # app + db 서비스
├── docker-compose.dev.yml        # 개발용 오버라이드
└── backup.sh                     # pg_dump 백업 스크립트
```

---

## 데이터 모델 및 DB 스키마

### 주요 엔티티 관계

```
Department (1) ──< Team (0..N)
Department (1) ──< Employee (0..N)
Team (1) ──< Employee (0..N)
Department (1) ──< MeetingRoom (0..N)  [담당 부서]
MeetingRoom (1) ──< RoomEquipment (0..N)
Meeting (N) >──< Employee (M)  through MeetingAttendee
Meeting (1) ──< MeetingFile (0..N)
Meeting (1) ──< MeetingHistory (0..N)
Employee (1) ──< AuditLog (0..N)
```

### 핵심 인덱스 전략

```sql
-- 회의실 중복 예약 검사 (가장 빈번한 쿼리)
CREATE INDEX idx_meeting_room_date ON meeting (room_id, date, status)
  WHERE status != 'CANCELLED';

-- 회의 목록 필터링
CREATE INDEX idx_meeting_status_date ON meeting (status, date DESC);
CREATE INDEX idx_meeting_dept ON meeting (dept_id);

-- 참석자 검색
CREATE INDEX idx_attendee_meeting ON meeting_attendee (meeting_id);
CREATE INDEX idx_attendee_employee ON meeting_attendee (employee_id);

-- 감사 로그 조회
CREATE INDEX idx_audit_actor_ts ON audit_log (actor, created_at DESC);
CREATE INDEX idx_audit_target ON audit_log (target_table, target_id);

-- 직원 검색 (참석자 선택)
CREATE INDEX idx_employee_name ON employee USING gin(name gin_trgm_ops);
CREATE INDEX idx_employee_status ON employee (status) WHERE status = 'ACTIVE';

-- 이력 테이블 조회
CREATE INDEX idx_*_history_target ON *_history (target_id, changed_at DESC);

-- ETL 동기화
CREATE UNIQUE INDEX idx_staging_emp_no ON employee_staging (emp_no);
```

---

## API 엔드포인트 목록

### 인증 (`/api/auth`)
| Method | Path | 설명 | 권한 |
|--------|------|------|------|
| POST | `/api/auth/login` | 로그인 (행번+비밀번호) | 누구나 |
| POST | `/api/auth/logout` | 로그아웃 (RT 쿠키 삭제) | 로그인 필요 |
| POST | `/api/auth/token/refresh` | AT 재발급 | RT 쿠키 필요 |
| POST | `/api/auth/password/change` | 비밀번호 변경 | 로그인 필요 |
| POST | `/api/auth/admin/reset-password` | admin 비밀번호 초기화 | ADMIN_RESET_TOKEN |

### 직원 (`/api/employees`)
| Method | Path | 설명 | 권한 |
|--------|------|------|------|
| GET | `/api/employees` | 목록 (페이지네이션, 검색) | admin |
| GET | `/api/employees/search` | 참석자 선택용 검색 | 로그인 필요 |
| GET | `/api/employees/{emp_no}` | 상세 | admin |
| PUT | `/api/employees/{emp_no}` | 정보 수정 | admin |
| DELETE | `/api/employees/{emp_no}` | 퇴직 처리 | admin |

### 부서·팀 (`/api/departments`, `/api/teams`)
| Method | Path | 설명 | 권한 |
|--------|------|------|------|
| GET | `/api/departments` | 전체 목록 | 로그인 필요 |
| POST | `/api/departments` | 생성 | admin |
| PUT | `/api/departments/{id}` | 수정 | admin |
| DELETE | `/api/departments/{id}` | 삭제 | admin |
| GET | `/api/departments/{id}/teams` | 팀 목록 | 로그인 필요 |
| POST | `/api/teams` | 팀 생성 | admin |
| PUT | `/api/teams/{id}` | 팀 수정 | admin |
| DELETE | `/api/teams/{id}` | 팀 삭제 | admin |

### 회의실 (`/api/meeting-rooms`)
| Method | Path | 설명 | 권한 |
|--------|------|------|------|
| GET | `/api/meeting-rooms` | 목록 (상태 필터) | 로그인 필요 |
| POST | `/api/meeting-rooms` | 생성 | room_manager / admin |
| GET | `/api/meeting-rooms/{id}` | 상세 + 집기 포함 | 로그인 필요 |
| PUT | `/api/meeting-rooms/{id}` | 수정 | room_manager(담당) / admin |
| DELETE | `/api/meeting-rooms/{id}` | 삭제 | admin |
| GET | `/api/meeting-rooms/{id}/schedule` | 특정 날짜 예약 현황 | 로그인 필요 |
| POST | `/api/meeting-rooms/{id}/equipment` | 집기 추가 | room_manager / admin |
| PUT | `/api/meeting-rooms/{id}/equipment/{eq_id}` | 집기 수정 | room_manager / admin |
| DELETE | `/api/meeting-rooms/{id}/equipment/{eq_id}` | 집기 삭제 | room_manager / admin |

### 회의 채널 (`/api/meetings`)
| Method | Path | 설명 | 권한 |
|--------|------|------|------|
| GET | `/api/meetings` | 목록 (다중 필터, 페이지네이션) | 로그인 필요 |
| POST | `/api/meetings` | 생성 | 로그인 필요 |
| GET | `/api/meetings/{id}` | 상세 | 로그인 필요 |
| PUT | `/api/meetings/{id}` | 수정 | 부서원 / admin |
| DELETE | `/api/meetings/{id}` | 삭제 | 부서원 / admin |
| PATCH | `/api/meetings/{id}/status` | 상태 변경 | 부서원 / admin |
| POST | `/api/meetings/{id}/files` | 파일 업로드 (multipart) | 부서원 / admin |
| GET | `/api/meetings/{id}/files` | 파일 목록 | 참석자 / 부서원 / admin |
| GET | `/api/meetings/{id}/files/{file_id}/download` | 파일 다운로드 | 참석자 / 부서원 / admin |
| DELETE | `/api/meetings/{id}/files/{file_id}` | 파일 삭제 | 부서원 / admin |
| POST | `/api/meetings/{id}/messages` | 참석자 메시지 전송 | 참석자 / 부서원 |

### 관리자 (`/api/admin`)
| Method | Path | 설명 | 권한 |
|--------|------|------|------|
| GET | `/api/admin/audit-logs` | 감사 로그 조회 | admin |
| GET | `/api/admin/message-logs` | 메시지 발송 이력 | admin |
| POST | `/api/admin/message-logs/{id}/resend` | 실패 메시지 재발송 | admin |
| PUT | `/api/admin/employees/{emp_no}/permissions` | 권한 부여/해제 | admin |
| POST | `/api/admin/sync/run` | 배치 동기화 즉시 실행 | admin |
| GET | `/api/admin/staging` | 임시원장 조회 (Mock) | admin |
| PUT | `/api/admin/staging` | 임시원장 편집 (Mock) | admin |

### 기타
| Method | Path | 설명 | 권한 |
|--------|------|------|------|
| GET | `/api/health` | 헬스체크 (DB 연결 확인) | 누구나 |
| GET | `/dev/messages` | Mock 메시지 조회 UI | dev 환경만 |

---

## 패턴 및 설계 규칙

### 3계층 구조
- **라우터**: 요청 파싱, 응답 직렬화, 권한 의존성 주입만 담당. 비즈니스 로직 없음
- **서비스**: 비즈니스 규칙, 유효성 검사, 트랜잭션 조율. DB 세션은 리포지토리에만 전달
- **리포지토리**: SQLAlchemy 세션을 통한 순수 DB 접근. 비즈니스 로직 없음

### 의존성 주입 패턴
```python
# dependencies.py
async def get_current_user(token: str = Depends(oauth2_scheme), db = Depends(get_db)) -> Employee: ...
async def require_admin(user = Depends(get_current_user)) -> Employee: ...
async def require_room_manager(user = Depends(get_current_user)) -> Employee: ...
async def require_active_user(user = Depends(get_current_user)) -> Employee:
    # is_initial_password=true인 경우 비밀번호 변경 API 제외 모두 403
    ...
```

### 이력 기록 패턴
- 각 Repository의 `create`, `update`, `delete` 메서드에서 해당 `*History` 테이블에 이력 기록
- 이력 기록과 원본 변경은 **동일 트랜잭션** 내에서 처리 (원자성 보장)
- 변경자 정보는 서비스 계층에서 전달 (Repository는 변경자를 인자로 받음)

### 감사 로그 패턴
```python
# audit_middleware.py
# 모든 API 요청에서 응답 완료 후 AuditLog INSERT
# 로그인 성공/실패는 auth_service에서 직접 기록
# 파일 다운로드는 meeting 라우터에서 직접 기록
```
- AuditLog INSERT 실패가 원래 응답을 실패시키지 않음 (best-effort)
- 감사 로그는 별도 DB 세션으로 기록 (메인 트랜잭션과 분리)

---

## 데이터 흐름

### 회의 생성 흐름 (중복 예약 포함)
```
POST /api/meetings
  → 라우터: 요청 파싱, get_current_user 검증
  → meeting_service.create_meeting()
      → meeting_repo.check_room_availability()  ← SELECT FOR UPDATE on room row
          → 겹침 있으면 HTTPException 409
      → meeting_repo.create()                   ← INSERT meeting + attendees (트랜잭션)
      → meeting_history_repo.record()           ← 동일 트랜잭션
      → notification_service.notify_created()   ← 트랜잭션 커밋 후 비동기 발송
  → 응답 반환
  → audit_middleware: AuditLog INSERT (별도 세션)
```

### 파일 업로드 흐름
```
POST /api/meetings/{id}/files (multipart/form-data)
  → 파일 크기·확장자·MIME 검사 (서비스 레이어)
  → 임시 위치에 파일 저장 (스트리밍)
  → DB 트랜잭션 시작
      → meeting_file_repo.create() (메타데이터 INSERT)
      → 임시 파일 → 최종 경로 이동
  → 트랜잭션 커밋
  → 실패 시: DB 롤백 + 임시 파일 삭제
```

### 인증 흐름
```
로그인 POST /api/auth/login
  → auth_service: 직원원장 조회, bcrypt 검증
  → 실패: 실패 횟수 +1, 5회면 locked_until 설정, AuditLog LOGIN_FAIL
  → 성공: 실패 횟수 초기화, AT + RT 발급, AuditLog LOGIN
  → 응답: { access_token, token_type, is_initial_password }
  → RT: HttpOnly 쿠키 Set-Cookie

토큰 갱신 POST /api/auth/token/refresh
  → RT 쿠키 검증 (만료·블랙리스트 확인)
  → 유효: 새 AT 발급 (RT는 갱신하지 않음, 만료 시점 유지)
  → 무효: 401 → 클라이언트 로그인 페이지 이동
  → 동시 갱신 경합: 첫 번째 요청만 성공, 나머지는 401 반환 (RT 1회 사용 원칙)
```

### ETL 동기화 흐름
```
[운영] ETL 툴 → employee_staging TRUNCATE + INSERT (매일 새벽)
[개발] Admin UI → employee_staging CRUD

APScheduler cron (매일 02:00 KST)
  → sync_service.run()
      → 안전 검사: staging이 비어 있으면 중단 (AuditLog BATCH_RUN + 경고 기록)
      → 트랜잭션 시작
          → staging vs employee 비교 (신규/변경/퇴직 분류)
          → Employee INSERT/UPDATE, EmployeeHistory 기록
          → 퇴직 처리 (status=RETIRED)
          → staging 초기화 (TRUNCATE)
      → 트랜잭션 커밋
      → AuditLog BATCH_RUN 기록 (처리 건수 포함)
  → 실패: 트랜잭션 롤백, AuditLog에 에러 기록, 다음 날 재시도
```

### 알림 발송 흐름
```
notification_service.notify(recipients, message, ref)
  → 재직 중인 수신자만 필터링
  → INTERNAL_MSG_API_URL 설정 여부 확인
      → 설정됨: HTTP POST (타임아웃 5초)
          → 실패 시 1분 간격 최대 3회 재시도 (백그라운드 태스크)
      → 미설정: Mock 처리
  → MessageLog INSERT (성공/실패 무관)
```

---

## 동시성 제어

### 회의실 중복 예약 방지 (비관적 잠금)
```python
# meeting_repo.check_room_availability()
# 해당 회의실 ID로 특정 날짜 범위를 잠금하여 Race condition 방지
SELECT id FROM meeting_room WHERE id = :room_id FOR UPDATE;
-- 이후 회의 시간 겹침 검사 수행
```
- 같은 회의실에 동시 예약 요청이 오면 하나는 잠금 대기 → 앞선 요청 커밋 후 뒤 요청이 겹침 감지

### Refresh Token 동시 갱신 방지
- RT에 `jti` (JWT ID) 포함
- 갱신 성공 시 `used_tokens` DB 테이블에 `jti` INSERT
- 동일 `jti`로 재갱신 시도 시 → 이미 사용된 토큰 → 401

---

## 에러 응답 형식 (통일)

```json
{
  "error": {
    "code": "ROOM_BOOKING_CONFLICT",
    "message": "해당 시간대에 이미 예약된 회의가 있습니다",
    "detail": {
      "conflicting_meeting": {
        "id": "uuid",
        "title": "임원 보고",
        "start_time": "14:00",
        "end_time": "16:00"
      }
    }
  }
}
```

**에러 코드 목록:**
| HTTP | code | 상황 |
|------|------|------|
| 400 | INVALID_REQUEST | 요청 형식 오류 |
| 401 | INVALID_CREDENTIALS | 인증 실패 |
| 401 | TOKEN_EXPIRED | 토큰 만료 |
| 403 | FORBIDDEN | 권한 없음 |
| 403 | FORCE_PASSWORD_CHANGE | 비밀번호 변경 필요 |
| 403 | ACCOUNT_DISABLED | 퇴직 직원 |
| 409 | ROOM_BOOKING_CONFLICT | 중복 예약 |
| 409 | ROOM_NOT_AVAILABLE | 폐쇄 회의실 |
| 409 | MEETING_ALREADY_CLOSED | 완료·취소 회의 수정 불가 |
| 409 | FILE_LIMIT_EXCEEDED | 파일 수 초과 |
| 409 | CONFLICT | 일반 충돌 |
| 413 | FILE_TOO_LARGE | 파일 크기 초과 |
| 415 | UNSUPPORTED_MEDIA_TYPE | 허용되지 않은 파일 형식 |
| 422 | INVALID_TIME_RANGE | 종료 < 시작 |
| 422 | PAST_MEETING_TIME | 과거 시간 회의 |
| 422 | MEETING_TOO_SHORT | 30분 미만 |
| 422 | MEETING_TOO_LONG | 8시간 초과 |
| 422 | EMPTY_MESSAGE | 빈 메시지 |
| 423 | ACCOUNT_LOCKED | 계정 잠금 (헤더에 unlock_at 포함) |
| 500 | INTERNAL_ERROR | 서버 내부 오류 |

---

## 환경 변수

```python
# backend/app/config.py
class Settings(BaseSettings):
    database_url: str                        # postgresql+asyncpg://...
    secret_key: str                          # JWT 서명 키 (최소 32바이트)
    frontend_origin: str                     # CORS 허용 출처
    app_env: str = "development"             # development | production
    internal_msg_api_url: str = ""           # 비어 있으면 Mock 모드
    internal_msg_api_timeout: int = 5        # 초
    upload_dir: str = "/app/uploads"
    max_upload_size_mb: int = 50
    admin_reset_token: str = ""              # admin 비밀번호 초기화 토큰
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    login_max_attempts: int = 5
    login_lock_minutes: int = 30
    sync_cron: str = "0 2 * * *"            # 매일 02:00 KST

    class Config:
        env_file = ".env"
```

---

## DB 연결 풀 설정

```python
# backend/app/db.py
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,       # 기본 10
    max_overflow=settings.db_max_overflow,  # 기본 20 (초과 시 대기)
    pool_timeout=settings.db_pool_timeout,  # 30초 대기 후 TimeoutError
    pool_pre_ping=True,                    # 연결 유효성 사전 확인 (끊긴 연결 자동 교체)
    echo=settings.app_env == "development",
)
```

- `pool_pre_ping=True`: 폐쇄망에서 DB 재시작 후 풀 내 죽은 연결 자동 교체
- 커넥션 풀 고갈 시: `TimeoutError` → `503 SERVICE_UNAVAILABLE`

---

## 애플리케이션 로깅

- 라이브러리: `structlog` (JSON 구조화 로그)
- 로그 레벨: 개발 `DEBUG`, 운영 `INFO`
- 출력: `stdout` (Docker logs에서 수집)
- 포함 필드: `timestamp`, `level`, `logger`, `request_id`, `user`, `message`
- 에러 발생 시 스택 트레이스 포함
- 감사 로그(AuditLog DB 테이블)와 애플리케이션 로그(stdout)는 용도가 다름

```python
# 요청 ID: X-Request-ID 헤더 또는 UUID 자동 생성
# request_id_middleware.py에서 컨텍스트 변수로 전파
```

---

## 보안

### HTTP 헤더
```python
# main.py - 모든 응답에 보안 헤더 추가
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'
Strict-Transport-Security: max-age=31536000  # HTTPS 환경에만
```

### SQL Injection 방지
- SQLAlchemy ORM + 파라미터 바인딩 사용 필수
- Raw SQL 사용 금지. 불가피한 경우 `text()` + `bindparams()` 사용

### 파일 업로드 보안
- 저장 경로 외부 노출 금지 (디렉토리 트래버설 방지)
- 저장명: `{uuid}_{sanitized_filename}` (특수문자, `..`, `/` 제거)
- 다운로드 응답: `Content-Disposition: attachment` (브라우저 실행 차단)
- MIME 타입 검사: 확장자 + python-magic 라이브러리로 실제 파일 타입 확인

### CSRF 방지
- Refresh Token: `SameSite=Strict` HttpOnly 쿠키
- 상태 변경 요청: `Authorization: Bearer` 헤더 방식 (쿠키 기반 공격 차단)

---

## 헬스체크

```
GET /api/health
응답: { "status": "ok", "db": "ok", "timestamp": "..." }
DB 연결 실패 시: { "status": "degraded", "db": "error" } + HTTP 503
```

- Docker HEALTHCHECK 지시자에 연결하여 컨테이너 상태 관리

---

## SPA 라우팅

- 해시 기반 라우팅(`/#/meetings`, `/#/admin`) 사용
- 장점: FastAPI의 catch-all 없이도 정적 파일 서빙으로 동작 (새로고침 시 404 없음)
- Svelte에서 `window.location.hash` 또는 `svelte-routing` 라이브러리 사용

```python
# main.py: 정적 파일 서빙
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")
# html=True가 SPA fallback(index.html 반환) 역할
```

---

## Docker 배포

### Dockerfile (멀티스테이지)
```dockerfile
# Stage 1: Svelte 빌드
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python 앱 + 정적 파일
FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ .
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
EXPOSE 8000
HEALTHCHECK CMD curl -f http://localhost:8000/api/health || exit 1
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml
```yaml
services:
  app:
    image: meeting-room:latest
    env_file: .env
    ports: ["8000:8000"]
    volumes:
      - uploads:/app/uploads
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    env_file: .env                        # POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/backup:/backup           # 백업 저장 위치
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $POSTGRES_USER"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  postgres_data:
  uploads:
```

### 폐쇄망 배포 절차
```bash
# 인터넷 환경
docker compose build
docker save meeting-room:latest postgres:16-alpine | gzip > images.tar.gz

# 폐쇄망 전달 후
docker load < images.tar.gz
docker compose up -d
docker compose exec app uv run alembic upgrade head  # 최초 실행 또는 마이그레이션
```

### DB 백업
```bash
# docker/backup.sh (cron으로 매일 새벽 실행)
docker compose exec db pg_dump -U $POSTGRES_USER $POSTGRES_DB \
  | gzip > /backup/meeting_room_$(date +%Y%m%d).sql.gz
# 30일 이상 된 백업 자동 삭제
find /backup -name "*.sql.gz" -mtime +30 -delete
```

---

## 배치 스케줄러 (APScheduler)

```python
# scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler(timezone="Asia/Seoul")

@scheduler.scheduled_job("cron", hour=2, minute=0)
async def sync_employees():
    await sync_service.run()

# app startup 이벤트에서 scheduler.start()
# app shutdown 이벤트에서 scheduler.shutdown()
```

**배치 실패 처리:**
- 예외 발생 시 전체 트랜잭션 롤백
- AuditLog에 `BATCH_RUN` + `error_message` 기록
- 다음 스케줄 실행 시 재시도 (별도 재시도 로직 없음)
- Admin이 즉시 재실행 원할 시: `POST /api/admin/sync/run`

---

## 프론트엔드 UX 패턴

### fetch 래퍼 — 토큰 자동 갱신 (Silent Refresh)

```javascript
// lib/api/client.js 핵심 로직
let isRefreshing = false;
let pendingRequests = [];  // 갱신 중 대기 중인 요청들

async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    ...options,
    headers: { Authorization: `Bearer ${getAccessToken()}`, ...options.headers },
  });

  if (res.status === 401) {
    // 이미 갱신 중이면 갱신 완료까지 대기
    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        pendingRequests.push({ resolve, reject, path, options });
      });
    }

    isRefreshing = true;
    try {
      const newToken = await refreshAccessToken();  // POST /api/auth/token/refresh
      setAccessToken(newToken);
      pendingRequests.forEach(({ resolve, path, options }) =>
        resolve(request(path, options))  // 원래 요청 재시도
      );
      pendingRequests = [];
      return request(path, options);    // 현재 요청도 재시도
    } catch {
      pendingRequests.forEach(({ reject }) => reject(new Error("SESSION_EXPIRED")));
      pendingRequests = [];
      navigateTo("/login");             // 로그인 페이지 이동
      showToast("로그인 세션이 만료되었습니다. 다시 로그인해 주세요.", "error");
    } finally {
      isRefreshing = false;
    }
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: { code: "UNKNOWN", message: res.statusText } }));
    throw new ApiError(err.error.code, err.error.message, err.error.detail, res.status);
  }
  return res.json();
}
```

- 동시 요청이 여러 개일 때 갱신 요청은 1번만 발생 (pendingRequests 대기열)
- AT는 메모리(Svelte store) 보관. 페이지 새로고침 시 RT 쿠키로 재발급
- 페이지 로드 시 `auth.js`가 먼저 `/api/auth/token/refresh` 호출 → 성공 시 AT 세팅

### Toast 시스템

```javascript
// lib/stores/toast.js
import { writable } from 'svelte/store';

export const toasts = writable([]);

export function showToast(message, type = 'success', duration = type === 'error' ? 5000 : 3000) {
  const id = crypto.randomUUID();
  toasts.update(list => {
    const next = [...list, { id, message, type }];
    return next.length > 3 ? next.slice(next.length - 3) : next;  // 최대 3개
  });
  if (duration > 0) {
    setTimeout(() => dismissToast(id), duration);
  }
  return id;
}

export function dismissToast(id) {
  toasts.update(list => list.filter(t => t.id !== id));
}
```

- `AppShell.svelte`에서 `{#each $toasts}` 렌더링
- 경고 타입(`warning`)은 `duration = 0` (수동 닫기 필수)
- 타입별 스타일: success=초록, error=빨강, warning=노랑, info=중립

### 로딩 상태 관리

```javascript
// 페이지 레벨 로딩 패턴
let loading = true;
let data = null;

onMount(async () => {
  try {
    data = await meetings.getList(filters);
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    loading = false;
  }
});
```

```svelte
<!-- 스켈레톤 컴포넌트 사용 패턴 -->
{#if loading}
  <SkeletonTable rows={5} />
{:else if data.items.length === 0}
  <EmptyState message="예정된 회의가 없습니다." />
{:else}
  <MeetingTable items={data.items} />
{/if}
```

**스켈레톤 스타일**: `rounded bg-neutral-800 animate-pulse h-4 w-full`

### 폼 Dirty State (미저장 경고)

```javascript
// 회의 폼에서 사용
let initialValues = { title: '', date: '', ... };
let currentValues = { ...initialValues };
$: isDirty = JSON.stringify(currentValues) !== JSON.stringify(initialValues);

// 페이지 이탈 감지
onMount(() => {
  const handleBeforeUnload = (e) => {
    if (isDirty) {
      e.preventDefault();
      e.returnValue = '';  // 브라우저 기본 확인 다이얼로그
    }
  };
  window.addEventListener('beforeunload', handleBeforeUnload);
  return () => window.removeEventListener('beforeunload', handleBeforeUnload);
});

// 해시 라우터 내부 이동도 차단
function navigateAway(path) {
  if (isDirty) {
    if (!confirm('변경 사항이 저장되지 않습니다. 이동하시겠습니까?')) return;
  }
  navigateTo(path);
}
```

- 폼 제출 성공 또는 [취소] 버튼 클릭 시 → `isDirty = false` 설정 후 이동

### 파일 업로드 Progress

```javascript
// XMLHttpRequest 사용 (fetch는 upload progress 미지원)
async function uploadFile(meetingId, file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });
    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText));
      else reject(new Error(JSON.parse(xhr.responseText)?.error?.message));
    });
    xhr.addEventListener('error', () => reject(new Error('업로드 실패')));
    xhr.open('POST', `/api/meetings/${meetingId}/files`);
    xhr.setRequestHeader('Authorization', `Bearer ${getAccessToken()}`);
    const formData = new FormData();
    formData.append('file', file);
    xhr.send(formData);
  });
}
```

- 클라이언트 사전 검사: 파일 크기(50MB), 확장자 → 서버 요청 전 차단
- 다중 파일 순차 업로드 (병렬 업로드 아님 → 서버 부하 방지)
- 각 파일의 진행률 개별 표시

### 에러 표시 패턴

```javascript
// ApiError 클래스
class ApiError extends Error {
  constructor(code, message, detail, status) {
    super(message);
    this.code = code;
    this.detail = detail;
    this.status = status;
  }
}
```

```svelte
<!-- 컴포넌트에서 에러 처리 -->
<script>
let submitError = null;

async function handleSubmit() {
  submitError = null;
  try {
    await meetings.create(formData);
    showToast('회의가 생성되었습니다.');
    navigateTo('/meetings');
  } catch (e) {
    if (e.code === 'ROOM_BOOKING_CONFLICT') {
      // 충돌 정보 우측 패널에 표시
      conflictMeeting = e.detail.conflicting_meeting;
      submitError = e.message;
    } else {
      showToast(e.message, 'error');
    }
  }
}
</script>

{#if submitError}
  <p class="text-sm text-red-400">{submitError}</p>
{/if}
```

**에러 표시 위치 기준:**
- 폼 제출 실패 (비즈니스 에러): 폼 상단 인라인 에러 메시지
- 중복 예약: 인라인 에러 + 우측 가용성 패널 업데이트
- 권한 오류·서버 오류: 토스트만
- 필드 유효성 오류: 해당 필드 아래 인라인

### 참석자 선택기 (AttendeeSelector) 구현 패턴

```javascript
let searchQuery = '';
let searchResults = [];
let searchTimeout = null;

function onSearchInput(e) {
  searchQuery = e.target.value;
  clearTimeout(searchTimeout);
  if (searchQuery.length < 1) { searchResults = []; return; }
  searchTimeout = setTimeout(async () => {
    searchResults = await employees.search(searchQuery);  // 300ms 디바운스
  }, 300);
}
```

- 검색어 1자 이상 입력 시 검색 (0자 = 드롭다운 닫기)
- 드롭다운은 검색 결과 최대 10건 (이름 + 부서 + 직급 표시)
- `Escape` 키 → 드롭다운 닫기
- `ArrowDown/Up` → 드롭다운 항목 포커스 이동
- `Enter` → 포커스된 항목 선택

### 회의실 가용성 패널 구현 패턴

- 날짜·회의실 선택 시 `GET /api/meeting-rooms/{id}/schedule?date=YYYY-MM-DD` 호출
- 응답: 해당 날짜의 `예정` 상태 회의 목록 (시작~종료 시간)
- UI: 09:00~18:00 타임라인, 예약된 구간은 색상 블록, 비어있는 구간은 회색
- 현재 폼에서 선택한 시간 구간 → 파란색 반투명 오버레이
- 충돌 구간 → 빨간색으로 강조

---

## CORS 설정

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- `allow_origins`에 `"*"` 와일드카드 사용 금지
- 개발 환경: `FRONTEND_ORIGIN=http://localhost:5173`
- 운영 환경: 실제 서버 IP 또는 도메인
