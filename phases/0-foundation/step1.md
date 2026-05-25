# Step 1: db-models

## 읽어야 할 파일

먼저 아래 파일들을 읽고 데이터 모델과 설계 의도를 파악하라:

- `/docs/PRD.md` — 섹션 1~7: 모든 도메인 엔티티, 필드 제약, 상태 값, 비즈니스 규칙
- `/docs/ARCHITECTURE.md` — "데이터 모델 및 DB 스키마", "핵심 인덱스 전략"
- `/docs/ADR.md` — ADR-003 (PostgreSQL+SQLAlchemy 선택 이유), ADR-012 (감사 로그 전용 테이블), ADR-016 (이력 테이블)
- `phases/0-foundation/index.json` — step 0 summary 확인
- `backend/app/` — step 0에서 생성된 구조 확인

이전 step에서 만들어진 코드를 꼼꼼히 읽고, 디렉토리 구조를 확인한 뒤 작업하라.

## 작업

### 목표
SQLAlchemy 2.x async 스타일로 모든 ORM 모델을 정의하고, Alembic 마이그레이션으로 스키마를 생성한다. DB 연결 설정은 다음 step(core-infra)에서 하므로, 이 step에서는 모델 정의에만 집중한다.

### `backend/app/models/base.py`

```python
from sqlalchemy.orm import DeclarativeBase, MappedColumn
from sqlalchemy import func
import datetime

class Base(DeclarativeBase):
    pass

# 공통 타임스탬프 믹스인
class TimestampMixin:
    created_at: MappedColumn[datetime.datetime]  # server_default=func.now()
    updated_at: MappedColumn[datetime.datetime]  # onupdate=func.now()
```

### `backend/app/models/org.py` — 조직 모델

아래 모델을 정의한다:

**Department**
- `code: str` — PK, 최대 20자
- `name: str` — NOT NULL, 최대 100자
- `status: str` — ENUM('ACTIVE', 'INACTIVE'), 기본 'ACTIVE'
- relationships: teams, employees, meeting_rooms

**Team**
- `code: str` — PK, 최대 20자
- `name: str` — NOT NULL, 최대 100자
- `dept_code: str` — FK → Department, NOT NULL
- `status: str` — ENUM('ACTIVE', 'INACTIVE'), 기본 'ACTIVE'
- relationships: employees

**Employee** (직원원장)
- `emp_no: str` — PK, CHAR(6)
- `name: str` — NOT NULL, 최대 50자
- `dept_code: str` — FK → Department, NOT NULL
- `team_code: str` — FK → Team, nullable
- `rank: str` — nullable, 최대 30자
- `status: str` — ENUM('ACTIVE', 'RETIRED'), 기본 'ACTIVE'
- `password_hash: str` — NOT NULL
- `is_admin: bool` — 기본 False
- `is_room_manager: bool` — 기본 False
- `is_initial_password: bool` — 기본 True
- `login_fail_count: int` — 기본 0
- `locked_until: datetime` — nullable
- TimestampMixin 포함

**EmployeeStaging** (ETL 임시원장)
- `emp_no: str` — PK, CHAR(6) (UNIQUE INDEX)
- `name: str`, `dept_code: str`, `team_code: str` (nullable), `rank: str` (nullable)
- ETL이 직접 TRUNCATE → INSERT하는 테이블. 비밀번호/권한 필드 없음

이력 테이블 3개 — **DepartmentHistory**, **TeamHistory**, **EmployeeHistory**:
- 공통 필드: `id: int` PK auto, `target_id: str`, `change_type: str` ENUM('CREATE','UPDATE','DELETE'), `before_data: dict` JSONB nullable, `after_data: dict` JSONB nullable, `changed_by: str`, `changed_at: datetime`

### `backend/app/models/room.py` — 회의실 모델

**MeetingRoom**
- `id: uuid` — PK (server_default=gen_random_uuid())
- `name: str` — 최대 100자, NOT NULL, UNIQUE
- `location: str` — 최대 200자, NOT NULL
- `status: str` — ENUM('NORMAL', 'TEMP_CLOSED', 'CLOSED'), 기본 'NORMAL'
- `dept_code: str` — FK → Department, NOT NULL
- relationships: equipment, meetings

**RoomEquipment**
- `id: uuid` — PK
- `room_id: uuid` — FK → MeetingRoom, NOT NULL
- `name: str` — 최대 100자, NOT NULL
- `quantity: int` — NOT NULL, CHECK quantity >= 1
- `note: str` — TEXT, nullable
- UNIQUE constraint: (room_id, name)

이력 테이블 2개 — **MeetingRoomHistory**, **RoomEquipmentHistory** (공통 이력 구조 동일)

### `backend/app/models/meeting.py` — 회의 모델

**Meeting**
- `id: uuid` — PK
- `title: str` — 최대 200자, NOT NULL
- `date: datetime.date` — NOT NULL
- `start_time: datetime.time` — NOT NULL
- `end_time: datetime.time` — NOT NULL
- `room_id: uuid` — FK → MeetingRoom, NOT NULL
- `content: str` — TEXT, nullable
- `status: str` — ENUM('SCHEDULED', 'COMPLETED', 'CANCELLED'), 기본 'SCHEDULED'
- `dept_code: str` — FK → Department, NOT NULL (생성자 소속 부서 자동 설정)
- `created_by: str` — FK → Employee, NOT NULL
- TimestampMixin 포함
- relationships: attendees, files

**MeetingAttendee** (M:N 연결 테이블)
- `meeting_id: uuid` — FK → Meeting, PK 구성요소
- `emp_no: str` — FK → Employee, PK 구성요소
- `added_at: datetime` — server_default=func.now()

**MeetingFile**
- `id: uuid` — PK
- `meeting_id: uuid` — FK → Meeting, NOT NULL
- `original_name: str` — 최대 255자, NOT NULL
- `stored_name: str` — 최대 255자, NOT NULL, UNIQUE
- `file_size: int` — BIGINT, NOT NULL
- `mime_type: str` — 최대 100자, NOT NULL
- `uploaded_by: str` — FK → Employee, NOT NULL
- `uploaded_at: datetime` — server_default=func.now()

**MeetingHistory** (공통 이력 구조 동일)

### `backend/app/models/audit.py` — 감사 및 메시지 모델

**AuditLog**
- `id: int` — PK, BIGINT auto
- `actor: str` — 최대 20자 (행번 또는 'admin'), NOT NULL
- `action: str` — ENUM('LOGIN','LOGIN_FAIL','LOGOUT','CREATE','UPDATE','DELETE','DOWNLOAD','BATCH_RUN'), NOT NULL
- `target_table: str` — nullable
- `target_id: str` — nullable
- `detail: str` — TEXT, nullable
- `ip_address: str` — 최대 45자 (IPv6 포함), nullable
- `user_agent: str` — TEXT, nullable
- `created_at: datetime` — server_default=func.now(), NOT NULL

**MessageLog**
- `id: int` — PK, BIGINT auto
- `sender: str` — 최대 20자, NOT NULL
- `recipients: list` — JSONB, NOT NULL (행번 목록)
- `message: str` — TEXT, NOT NULL
- `ref_type: str` — 최대 20자, nullable
- `ref_id: str` — nullable
- `status: str` — ENUM('SENT', 'FAILED', 'MOCK'), 기본 'MOCK'
- `retry_count: int` — 기본 0
- `created_at: datetime` — server_default=func.now()

**AdminAccount** (admin 별도 계정)
- `id: int` — PK
- `username: str` — 'admin' 고정, UNIQUE
- `password_hash: str` — NOT NULL
- `is_initial_password: bool` — 기본 True
- `updated_at: datetime`

**UsedToken** (RT jti 블랙리스트)
- `jti: str` — PK, UUID 문자열
- `expires_at: datetime` — NOT NULL

### `backend/app/models/__init__.py`

모든 모델을 임포트하여 Alembic이 자동 감지할 수 있게 한다.

### Alembic 마이그레이션

```bash
cd backend
# .env 없이도 실행 가능하도록 env.py에 DATABASE_URL 하드코드 없이 처리
uv run alembic revision --autogenerate -m "initial schema"
```

생성된 마이그레이션 파일을 검토하여 모든 테이블, 인덱스, ENUM이 올바르게 포함되었는지 확인한다.

**필수 인덱스** (마이그레이션 파일에 포함되거나 모델에 `Index()` 선언):
```sql
-- 중복 예약 검사용 (partial index)
CREATE INDEX idx_meeting_room_date ON meeting (room_id, date, status)
  WHERE status != 'CANCELLED';
-- 회의 목록 필터
CREATE INDEX idx_meeting_status_date ON meeting (status, date DESC);
CREATE INDEX idx_meeting_dept ON meeting (dept_code);
-- 참석자
CREATE INDEX idx_attendee_employee ON meeting_attendee (emp_no);
-- 감사 로그
CREATE INDEX idx_audit_actor_ts ON audit_log (actor, created_at DESC);
CREATE INDEX idx_audit_target ON audit_log (target_table, target_id);
-- 이력 테이블 공통
-- 각 *_history 테이블에 (target_id, changed_at DESC) 인덱스
```

## Acceptance Criteria

```bash
# 모델 임포트 오류 없음
cd backend && uv run python -c "from app.models import *; print('models OK')"

# ruff 린트 통과
uv run ruff check app/models/

# 마이그레이션 파일이 생성되었는지 확인
ls alembic/versions/*.py

# 마이그레이션 적용 (로컬 PostgreSQL 또는 테스트 DB 필요)
# DATABASE_URL 환경 변수 설정 후:
# uv run alembic upgrade head
# uv run alembic check  ← "No new upgrade operations detected" 확인
```

## 검증 절차

1. 위 AC 커맨드를 실행한다 (DB 연결 필요한 항목은 DB 환경이 있을 때 확인).
2. 체크리스트:
   - 모든 FK 관계에 `ondelete` 전략이 명시되어 있는가? (CASCADE 또는 RESTRICT)
   - ENUM 타입이 PostgreSQL native ENUM 또는 VARCHAR CHECK 중 하나로 일관성 있게 정의되었는가?
   - `AuditLog`에 UPDATE/DELETE 메서드가 ORM 모델에 없는가? (읽기 전용 보장)
   - UUID PK 컬럼에 `server_default=text("gen_random_uuid()")` 설정이 있는가?
3. `phases/0-foundation/index.json` step 1 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "SQLAlchemy ORM 모델 전체 정의 완료 (org/room/meeting/audit). Alembic 초기 마이그레이션 생성. 주요 인덱스 포함"`
   - 실패 3회 → `"status": "error"`, `"error_message": "구체적 에러"`

## 금지사항

- `async_session.execute(text("raw SQL"))` 형태의 raw query 모델 정의 금지. 이유: ORM 모델 단계에서는 순수 선언적 방식만 사용
- `alembic upgrade head` 실행 후 DB 직접 수정 금지. 이유: 마이그레이션 파일이 유일한 스키마 진실의 근거
- `AuditLog` 모델에 `update()`, `delete()` ORM 메서드 추가 금지. 이유: 감사 로그는 불변
- 비밀번호 평문 저장 필드 추가 금지. `password_hash` 외 비밀번호 관련 필드 금지
