# Step 0: notification-backend

## 읽어야 할 파일

먼저 아래 파일들을 읽고 알림 설계를 파악하라:

- `/docs/PRD.md` — 섹션 7 "내부 메시지 알림" 전체 (발송 트리거, 메시지 템플릿, 재시도 규칙, Mock 모드)
- `/docs/ARCHITECTURE.md` — "데이터 흐름: 알림 발송", "API 엔드포인트 목록" (알림 섹션)
- `/docs/ADR.md` — ADR-013 (Mock 알림 서비스)
- `phases/4-meeting/index.json` — step 0~4 summary
- `backend/app/models/room.py` — MessageLog 모델
- `backend/app/models/org.py` — Employee 모델 (수신자 emp_no, 이름)
- `backend/app/config.py` — settings (INTERNAL_MSG_API_URL, APP_ENV)
- `backend/app/routers/meetings.py` — 알림 발송 트리거 시점 확인

## 작업

### 목표
회의 생성/수정/취소/완료 시 참석자에게 내부 메시지 알림을 발송한다. 실제 API가 없으면 Mock 모드로 동작한다. 실패 시 1분 간격 3회 재시도한다.

### `backend/app/services/notification_service.py`

```python
async def send_meeting_notification(
    meeting_id: str,
    event_type: str,   # "CREATED" | "UPDATED" | "CANCELLED" | "COMPLETED"
    recipients: list[str],  # emp_no 목록
    db: AsyncSession
) -> None:
    """
    1. 각 수신자별 MessageLog INSERT (status=PENDING)
    2. 백그라운드 태스크로 _dispatch_all(message_log_ids, db) 실행
       → 라우터에서 BackgroundTasks.add_task()로 호출
    """

async def _dispatch_all(log_ids: list[str], db: AsyncSession) -> None:
    """각 MessageLog에 대해 _send_one() 호출. 실패 시 재시도 스케줄"""

async def _send_one(log_id: str, db: AsyncSession) -> None:
    """
    MessageLog 조회 → status=SENDING으로 업데이트
    _build_message(log) → message dict 생성
    
    INTERNAL_MSG_API_URL이 비어있으면 Mock 모드:
      → 로그에 "MOCK: {message}" 출력, status=SENT
    
    실제 모드:
      → POST INTERNAL_MSG_API_URL 호출 (timeout=10초)
      → 성공 (2xx): status=SENT, sent_at=now()
      → 실패: status=FAILED, retry_count+=1
        → retry_count < 3: 60초 후 재시도 스케줄
        → retry_count >= 3: status=FAILED (포기)
    """

def _build_message(log: MessageLog) -> dict:
    """
    PRD 섹션 7 메시지 템플릿을 참고하여 이벤트 타입별 메시지 생성:
    
    CREATED:   "[회의 신청] {제목} | {날짜} {시작}-{종료} | {회의실}"
    UPDATED:   "[회의 수정] {제목} | {날짜} {시작}-{종료} | {회의실}"
    CANCELLED: "[회의 취소] {제목} | {날짜} | 취소 처리되었습니다."
    COMPLETED: "[회의 완료] {제목} | {날짜} | 완료 처리되었습니다."
    
    반환: {"recipient_emp_no": str, "message": str, "subject": str}
    """
```

### `backend/app/repositories/notification_repo.py`

```python
async def create_log(data: dict, db) -> MessageLog
    # status=PENDING으로 INSERT
async def get_log(log_id: str, db) -> MessageLog | None
async def update_log(log_id: str, data: dict, db) -> MessageLog
    # status, retry_count, sent_at, error_message 업데이트
async def get_my_notifications(emp_no: str, db, page=1, size=20) -> tuple[list[MessageLog], int]
    # 해당 직원이 수신자인 MessageLog 목록, 최신순
async def get_pending_logs(db) -> list[MessageLog]
    # status=PENDING or (status=FAILED and retry_count < 3), scheduler retry용
```

### `backend/app/routers/meetings.py` 수정

회의 생성/수정/취소/완료 각 엔드포인트에서 알림 발송 트리거 추가:

```python
# FastAPI BackgroundTasks 주입
@router.post("")
async def create_meeting_endpoint(
    ...,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_active_user)
):
    meeting = await meeting_repo.create_meeting(data, current_user.emp_no, db)
    recipients = [a.emp_no for a in meeting.attendees if a.emp_no != current_user.emp_no]
    background_tasks.add_task(
        notification_service.send_meeting_notification,
        meeting.id, "CREATED", recipients, db
    )
    return meeting
```

취소/완료 시에는 본인(취소자/완료자) 제외하고 나머지 참석자에게 발송.

### `backend/app/routers/notifications.py`

```python
router = APIRouter(prefix="/api/notifications", tags=["notifications"])

GET /api/notifications   → 내 알림 목록 (?page&size, require_active_user)
    # 최신순, 수신자=current_user.emp_no
    # 응답: PaginatedResponse[NotificationResponse]
```

### `backend/app/schemas/notification.py`

```python
class NotificationResponse(BaseModel):
    id: str
    event_type: str
    message: str
    status: str     # PENDING | SENDING | SENT | FAILED
    created_at: datetime
    sent_at: datetime | None
    model_config = ConfigDict(from_attributes=True)
```

### `backend/app/scheduler.py` 수정

실패한 알림 재시도 스케줄 추가 (매 5분):

```python
@scheduler.scheduled_job("interval", minutes=5)
async def retry_notifications():
    async for db in get_db():
        pending = await notification_repo.get_pending_logs(db)
        for log in pending:
            await notification_service._send_one(log.id, db)
        break
```

### `backend/app/main.py` 수정

notifications 라우터 등록.

### `backend/tests/test_notifications.py`

아래 시나리오를 테스트한다 (Mock 모드로 INTERNAL_MSG_API_URL 미설정):

- 회의 생성 시 참석자(주최자 제외)에게 MessageLog(PENDING) 생성
- Mock 모드에서 `_send_one` 호출 → status=SENT 로 변경
- 회의 취소 시 CANCELLED 이벤트 메시지 생성
- `GET /api/notifications` → 내 알림 목록 반환
- 메시지 빌드 결과가 PRD 템플릿 형식과 일치하는가

## Acceptance Criteria

```bash
cd backend
uv run pytest tests/test_notifications.py -v
uv run ruff check app/services/notification_service.py app/routers/notifications.py app/repositories/notification_repo.py
```

## 검증 절차

1. 테스트 전체 통과 확인
2. 체크리스트:
   - `INTERNAL_MSG_API_URL`이 없을 때 Mock 모드로 동작하여 실제 HTTP 요청을 보내지 않는가?
   - 알림 발송이 BackgroundTasks로 처리되어 메인 응답을 블로킹하지 않는가?
   - 메시지 빌드 시 회의 제목, 날짜, 시간, 회의실 정보가 모두 포함되는가?
   - `GET /api/notifications`가 요청자(current_user)의 알림만 반환하는가?
3. `phases/5-notification/index.json` step 0 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "알림 백엔드 완성: notification_service(Mock/실제모드)/BackgroundTasks비동기발송/3회재시도(1분간격)/5분주기scheduler retry/알림목록API"`

## 금지사항

- 알림 발송을 동기(blocking) 방식으로 구현 금지. 이유: 외부 API 호출이 메인 응답을 지연시킴
- `INTERNAL_MSG_API_URL` 미설정 시 예외 발생 금지. 이유: Mock 모드로 자동 전환해야 함
- retry 로직을 무한 재시도로 구현 금지. 이유: 최대 3회 후 FAILED 처리
- AuditLog와 MessageLog를 혼용 금지. 이유: MessageLog는 알림 전용, AuditLog는 시스템 감사 전용
