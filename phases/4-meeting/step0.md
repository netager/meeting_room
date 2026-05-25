# Step 0: meeting-backend

## 읽어야 할 파일

먼저 아래 파일들을 읽고 회의 도메인을 파악하라:

- `/docs/PRD.md` — 섹션 5 "회의" 전체 (Meeting, MeetingAttendee, 상태 전이, 예약 충돌, 수정 권한, 권한 규칙)
- `/docs/ARCHITECTURE.md` — "API 엔드포인트 목록" (회의 섹션), "데이터 흐름: 회의 생성", "이력 기록 패턴"
- `/docs/ADR.md` — ADR-009 (SELECT FOR UPDATE NOWAIT 예약 충돌), ADR-010 (상태 전이)
- `phases/0-foundation/index.json` — step 0~2 summary
- `phases/3-meeting-room/index.json` — step 0 summary
- `backend/app/models/room.py` — MeetingRoom, RoomEquipment
- `backend/app/models/org.py` — Employee (FK 참조)
- `backend/app/dependencies.py` — require_active_user, require_admin

## 작업

### 목표
회의 생성/수정/취소/완료 API와 Repository를 구현한다. 예약 충돌 방지(SELECT FOR UPDATE NOWAIT), 상태 전이 규칙, 수정 권한 검사를 포함한다.

### `backend/app/repositories/meeting_repo.py`

```python
async def get_meetings(
    db, emp_no: str = None, room_id: str = None,
    status: str = None, date_from: date = None, date_to: date = None,
    page: int = 1, size: int = 20
) -> tuple[list[Meeting], int]
    # emp_no 있으면: 해당 직원이 주최하거나 참석자인 회의만 반환
    # 반환: (items, total)

async def get_meeting(meeting_id: str, db) -> Meeting | None

async def create_meeting(data: dict, created_by: str, db) -> Meeting
    """
    1. 회의실 존재 여부 확인 → 없으면 404
    2. 회의실 status == NORMAL 인지 확인 → 아니면 422 "회의실이 사용 불가 상태입니다"
    3. SELECT FOR UPDATE NOWAIT — MeetingRoom 행 잠금
       → LockNotAvailable 예외 → 409 "예약 처리 중입니다. 잠시 후 다시 시도하세요."
    4. 동일 room_id + 날짜 + 시간 겹치는 SCHEDULED 회의 존재 여부 확인
       → 있으면 409 ROOM_BOOKING_CONFLICT
       (start_time < req.end_time AND end_time > req.start_time)
    5. Meeting INSERT, status=SCHEDULED
    6. MeetingAttendee INSERT (created_by 포함, 추가 참석자 목록)
    7. MeetingHistory(CREATE) 기록
    8. 잠금 해제 (트랜잭션 커밋)
    """

async def update_meeting(meeting_id: str, data: dict, updated_by: str, db) -> Meeting
    """
    수정 권한: created_by == updated_by 또는 is_admin
    → 아니면 403

    시간/회의실 변경 시에만 충돌 재검사 (create_meeting과 동일한 SELECT FOR UPDATE NOWAIT 로직)
    상태가 SCHEDULED가 아니면 수정 불가 → 422
    MeetingHistory(UPDATE) 기록
    """

async def cancel_meeting(meeting_id: str, cancelled_by: str, db) -> Meeting
    """
    권한: created_by == cancelled_by 또는 is_admin
    SCHEDULED → CANCELLED (최종 상태)
    MeetingHistory(UPDATE, before=SCHEDULED, after=CANCELLED) 기록
    """

async def complete_meeting(meeting_id: str, completed_by: str, db) -> Meeting
    """
    권한: is_admin만
    SCHEDULED → COMPLETED (최종 상태)
    MeetingHistory(UPDATE) 기록
    """

async def get_attendees(meeting_id: str, db) -> list[MeetingAttendee]
async def add_attendee(meeting_id: str, emp_no: str, added_by: str, db) -> MeetingAttendee
    # 이미 참석자이면 409 CONFLICT
    # SCHEDULED 상태 회의에만 추가 가능 → 아니면 422
async def remove_attendee(meeting_id: str, emp_no: str, removed_by: str, db) -> None
    # 주최자(created_by)는 삭제 불가 → 422
    # SCHEDULED 상태 회의에만 삭제 가능 → 아니면 422
```

### `backend/app/schemas/meeting.py`

```python
class MeetingCreate(BaseModel):
    title: str          # max 200자
    room_id: str
    meeting_date: date
    start_time: time
    end_time: time      # end_time > start_time 검증
    agenda: str | None  # max 2000자

class MeetingUpdate(BaseModel):
    title: str | None
    room_id: str | None
    meeting_date: date | None
    start_time: time | None
    end_time: time | None
    agenda: str | None

class AttendeeItem(BaseModel):
    emp_no: str; name: str; dept_code: str; rank: str | None
    model_config = ConfigDict(from_attributes=True)

class MeetingResponse(BaseModel):
    id: str; title: str; room_id: str; room_name: str
    meeting_date: date; start_time: time; end_time: time
    status: str; agenda: str | None
    created_by: str; created_by_name: str
    attendees: list[AttendeeItem] = []
    model_config = ConfigDict(from_attributes=True)

class MeetingListItem(BaseModel):
    id: str; title: str; room_name: str
    meeting_date: date; start_time: time; end_time: time
    status: str; attendee_count: int
    model_config = ConfigDict(from_attributes=True)

class PaginatedMeetings(BaseModel):
    items: list[MeetingListItem]; total: int; page: int; size: int; pages: int
```

### `backend/app/routers/meetings.py`

```python
router = APIRouter(prefix="/api/meetings", tags=["meetings"])

GET    /api/meetings            → 목록 (?my=true 시 내 회의만, ?status, ?date_from, ?date_to, require_active_user)
POST   /api/meetings            → 생성 (require_active_user)
GET    /api/meetings/{id}       → 상세 (참석자 포함, require_active_user)
PUT    /api/meetings/{id}       → 수정 (require_active_user, 내부에서 권한 검사)
DELETE /api/meetings/{id}       → 취소 (require_active_user, 내부에서 권한 검사)
POST   /api/meetings/{id}/complete → 완료 처리 (require_admin)

POST   /api/meetings/{id}/attendees           → 참석자 추가 (require_active_user)
DELETE /api/meetings/{id}/attendees/{emp_no}  → 참석자 삭제 (require_active_user)
```

**DELETE /api/meetings/{id}는 실제 삭제가 아닌 취소(CANCELLED) 처리임에 주의.**

### `backend/tests/test_meetings.py`

아래 시나리오를 테스트한다:

- 회의 생성 → SCHEDULED 상태, MeetingHistory(CREATE) 기록, created_by가 자동으로 참석자에 포함
- 동일 회의실 동일 시간 겹치는 예약 → 409 ROOM_BOOKING_CONFLICT
- 시간이 연속 붙어있을 때 (A: 09:00~10:00, B: 10:00~11:00) → 충돌 없음
- 주최자가 아닌 사람이 회의 수정 → 403
- admin이 다른 사람 회의 수정 → 성공
- SCHEDULED 회의 취소 → CANCELLED 상태 (재취소 불가 → 422)
- CANCELLED 회의 수정 시도 → 422
- 주최자(created_by)를 참석자에서 삭제 → 422
- NORMAL 상태가 아닌 회의실에 예약 → 422
- `?my=true` 필터: 내가 주최하거나 참석자인 회의만 반환

## Acceptance Criteria

```bash
cd backend
uv run pytest tests/test_meetings.py -v
uv run ruff check app/routers/meetings.py app/repositories/meeting_repo.py app/schemas/meeting.py
```

## 검증 절차

1. 테스트 전체 통과 확인
2. 체크리스트:
   - `SELECT FOR UPDATE NOWAIT` 가 적용되어 있는가? (meeting_repo.py에서 `with_for_update(nowait=True)` 사용)
   - 시간 겹침 공식이 `start_time < req.end_time AND end_time > req.start_time` 인가? (양 끝 시간이 정확히 붙으면 충돌 없음)
   - 취소(DELETE /api/meetings/{id}) 가 DB row를 실제 삭제하지 않고 status=CANCELLED 로만 바꾸는가?
   - `GET /api/meetings?my=true` 가 주최자이거나 참석자인 회의 모두 반환하는가?
3. `phases/4-meeting/index.json` step 0 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "회의 CRUD API 완성. SELECT FOR UPDATE NOWAIT 예약충돌방지/상태전이(SCHEDULED→CANCELLED/COMPLETED)/수정권한(주최자+admin)/참석자관리. 이력기록 포함"`

## 금지사항

- `DELETE /api/meetings/{id}`를 실제 DB 삭제로 구현 금지. 이유: 취소(status=CANCELLED) 소프트 처리
- 충돌 검사를 `SELECT FOR UPDATE` 없이 단순 SELECT로만 구현 금지. 이유: 동시 요청 시 TOCTOU 레이스 컨디션 발생
- COMPLETED 또는 CANCELLED 상태 회의의 수정/취소를 허용 금지. 이유: 최종 상태는 불변
- 시간 겹침 판단에서 `<=` 대신 `<` 를 잘못 사용하지 마라. 이유: 10:00~11:00과 11:00~12:00은 충돌 없음
