# Step 0: room-backend

## 읽어야 할 파일

먼저 아래 파일들을 읽고 회의실 도메인을 파악하라:

- `/docs/PRD.md` — 섹션 4 "회의실" 전체 (MeetingRoom, RoomEquipment, 상태 전이 규칙, 폐쇄 시 기존 예약 처리, 삭제 규칙)
- `/docs/ARCHITECTURE.md` — "API 엔드포인트 목록" (회의실 섹션), "이력 기록 패턴"
- `phases/0-foundation/index.json` — step 0~2 summary
- `phases/2-org/index.json` — step 0 summary (org_repo 패턴 참조)
- `backend/app/models/room.py` — MeetingRoom, RoomEquipment, *History 모델
- `backend/app/models/org.py` — Department (FK 참조)
- `backend/app/dependencies.py` — require_admin, require_room_manager, require_active_user

## 작업

### 목표
회의실과 집기원장의 CRUD API와 Repository를 구현한다. 상태 전이 규칙, 폐쇄 시 예약 경고, 삭제 제약을 포함한다.

### `backend/app/repositories/room_repo.py`

```python
async def get_meeting_rooms(db, status_filter=None, include_closed=False) -> list[MeetingRoom]
async def get_meeting_room(room_id: str, db) -> MeetingRoom | None
async def create_meeting_room(data: dict, changed_by: str, db) -> MeetingRoom
    # INSERT + MeetingRoomHistory(CREATE)
async def update_meeting_room(room_id: str, data: dict, changed_by: str, db) -> MeetingRoom
    """
    상태 변경 시 검증:
    - CLOSED → NORMAL/TEMP_CLOSED: is_admin=True인 경우만 허용
    - 상태가 NORMAL이 아닌 값으로 변경 시: 해당 회의실의 향후 SCHEDULED 회의 건수 조회
      → 있으면 변경은 허용하되 warnings 리스트 반환
    UPDATE + MeetingRoomHistory(UPDATE)
    반환: (MeetingRoom, warnings: list[str])
    """
async def delete_meeting_room(room_id: str, changed_by: str, db) -> None
    # 연결된 Meeting이 하나라도 있으면 HTTPException 409 CONFLICT
    # 연결된 RoomEquipment가 있으면 HTTPException 409 CONFLICT
    # DELETE + MeetingRoomHistory(DELETE)

async def get_equipment_list(room_id: str, db) -> list[RoomEquipment]
async def create_equipment(room_id: str, data: dict, changed_by: str, db) -> RoomEquipment
    # 동일 room_id + 동일 name → HTTPException 409 CONFLICT
    # INSERT + RoomEquipmentHistory(CREATE)
async def update_equipment(eq_id: str, data: dict, changed_by: str, db) -> RoomEquipment
async def delete_equipment(eq_id: str, changed_by: str, db) -> None

async def get_room_schedule(room_id: str, date: datetime.date, db) -> list[dict]
    """
    해당 날짜의 SCHEDULED 상태 회의 목록 반환
    반환: [{"meeting_id": uuid, "title": str, "start_time": time, "end_time": time}]
    회의실 가용성 패널 UI용 API
    """
```

### `backend/app/schemas/room.py`

```python
class MeetingRoomCreate(BaseModel):
    name: str  # max 100자
    location: str  # max 200자
    dept_code: str

class MeetingRoomUpdate(BaseModel):
    name: str | None; location: str | None; status: str | None; dept_code: str | None

class MeetingRoomResponse(BaseModel):
    id: str; name: str; location: str; status: str; dept_code: str
    equipment: list[RoomEquipmentResponse] = []
    model_config = ConfigDict(from_attributes=True)

class MeetingRoomUpdateResponse(BaseModel):
    room: MeetingRoomResponse
    warnings: list[str] = []  # 기존 예약이 있을 때 경고 메시지

class RoomEquipmentCreate(BaseModel):
    name: str  # max 100자
    quantity: int  # >= 1
    note: str | None

class ScheduleSlot(BaseModel):
    meeting_id: str; title: str; start_time: str; end_time: str
```

### `backend/app/routers/meeting_rooms.py`

```python
router = APIRouter(prefix="/api/meeting-rooms", tags=["meeting-rooms"])

GET    /api/meeting-rooms             → 목록 (?status=NORMAL,TEMP_CLOSED, require_active_user)
POST   /api/meeting-rooms             → 생성 (require_room_manager)
GET    /api/meeting-rooms/{id}        → 상세 (집기 포함, require_active_user)
PUT    /api/meeting-rooms/{id}        → 수정, 응답에 warnings 포함 (require_room_manager)
DELETE /api/meeting-rooms/{id}        → 삭제 (require_admin)
GET    /api/meeting-rooms/{id}/schedule → 특정 날짜 예약 현황 (?date=YYYY-MM-DD, require_active_user)

POST   /api/meeting-rooms/{id}/equipment          → 집기 추가 (require_room_manager)
PUT    /api/meeting-rooms/{id}/equipment/{eq_id}  → 집기 수정 (require_room_manager)
DELETE /api/meeting-rooms/{id}/equipment/{eq_id}  → 집기 삭제 (require_room_manager)
```

**room_manager 권한 검사 추가 규칙:**
- 해당 회의실의 `dept_code`가 로그인 사용자의 `dept_code`와 일치하지 않으면 403. admin은 예외

### `backend/tests/test_rooms.py`

아래 시나리오를 테스트한다:

- 회의실 생성 → MeetingRoomHistory(CREATE) 기록
- CLOSED 상태에서 NORMAL로 변경 → admin만 가능, 일반 room_manager는 403
- 기존 SCHEDULED 회의가 있는 상태에서 회의실 임시폐쇄 → 200 + warnings 반환
- 연결된 회의가 있는 회의실 삭제 시도 → 409
- 집기 중복 등록 → 409
- 집기 수량 0 입력 → 422
- 다른 부서 회의실을 room_manager가 수정 → 403

## Acceptance Criteria

```bash
cd backend
uv run pytest tests/test_rooms.py -v
uv run ruff check app/routers/meeting_rooms.py app/repositories/room_repo.py app/schemas/room.py
```

## 검증 절차

1. 테스트 전체 통과 확인
2. 체크리스트:
   - `PUT /meeting-rooms/{id}` 응답이 `{"room": {...}, "warnings": [...]}` 구조인가?
   - `GET /meeting-rooms/{id}/schedule` 응답이 해당 날짜의 예약 목록을 시작시간 오름차순으로 반환하는가?
   - `delete_meeting_room`에서 집기와 회의 양쪽 모두 존재 확인 후 각각 다른 에러 메시지를 반환하는가?
3. `phases/3-meeting-room/index.json` step 0 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "회의실/집기 CRUD API 완성. 상태 전이 규칙/폐쇄 경고/삭제 제약/예약 현황 API 포함. 이력 기록 포함"`

## 금지사항

- 회의실 상태 변경 시 기존 SCHEDULED 회의를 자동 취소하지 마라. 이유: PRD 규칙 — 담당자가 수동 처리
- 회의실 삭제를 물리적 삭제로 구현하되, 연결된 데이터 확인 없이 바로 DELETE 금지. 이유: 데이터 정합성
- `require_room_manager` 의존성에서 부서 일치 여부 확인을 생략 금지. 이유: 다른 부서 회의실을 관리할 수 없음
