# Step 0: audit-backend

## 읽어야 할 파일

먼저 아래 파일들을 읽고 감사 로그 및 관리자 API 설계를 파악하라:

- `/docs/PRD.md` — 섹션 9 "감사 로그 (AuditLog)", 섹션 3 "권한 체계" (admin 전용 기능)
- `/docs/ARCHITECTURE.md` — "이력 기록 패턴", "API 엔드포인트 목록" (admin 섹션)
- `phases/0-foundation/index.json` — step 2 summary (AuditMiddleware 위치 확인)
- `phases/2-org/index.json` — step 1 summary (admin.py 라우터 현황)
- `backend/app/models/room.py` — AuditLog 모델 (action, resource_type, resource_id, detail JSONB)
- `backend/app/routers/admin.py` — 현재 구현된 엔드포인트 확인

## 작업

### 목표
감사 로그 조회 API를 완성하고, admin 라우터를 정리한다. AuditLog는 쓰기(미들웨어 자동 기록)는 이미 구현되어 있으므로, 읽기(조회/검색) API만 추가한다.

### `backend/app/repositories/audit_repo.py`

```python
async def get_audit_logs(
    db,
    action: str = None,          # 예: "LOGIN", "CREATE", "UPDATE", "DELETE", "BATCH_RUN"
    resource_type: str = None,   # 예: "Meeting", "MeetingRoom", "Employee"
    actor_emp_no: str = None,    # 특정 직원의 액션만 필터
    date_from: date = None,
    date_to: date = None,
    page: int = 1,
    size: int = 50
) -> tuple[list[AuditLog], int]
    # 최신순(created_at DESC) 정렬
    # 반환: (items, total)

async def get_audit_log(log_id: str, db) -> AuditLog | None
```

### `backend/app/schemas/admin.py`

```python
class AuditLogResponse(BaseModel):
    id: str
    action: str
    resource_type: str | None
    resource_id: str | None
    actor_emp_no: str | None
    actor_name: str | None
    detail: dict | None       # JSONB — before/after 또는 기타 상세
    ip_address: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class PaginatedAuditLogs(BaseModel):
    items: list[AuditLogResponse]
    total: int; page: int; size: int; pages: int
```

### `backend/app/routers/admin.py` 완성

기존에 ETL 관련 엔드포인트(step 2-1에서 구현)에 이어 추가:

```python
# 감사 로그
GET /api/admin/audit-logs
    """
    require_admin
    ?action=&resource_type=&actor_emp_no=&date_from=&date_to=&page=&size=
    응답: PaginatedAuditLogs
    """

GET /api/admin/audit-logs/{log_id}
    """
    require_admin
    단건 조회 (detail JSONB 포함)
    """

# 직원 권한 관리 (2-org step 0에서 구현된 org_repo.update_permissions 사용)
PUT /api/admin/employees/{emp_no}/permissions
    """
    require_admin
    body: {"is_admin": bool, "is_room_manager": bool}
    응답: EmployeeResponse
    AuditLog("UPDATE", "Employee", emp_no, detail={"before": {...}, "after": {...}}) 기록
    """
```

### `backend/tests/test_admin.py`

아래 시나리오를 테스트한다:

- admin이 감사 로그 조회 → 200, 페이지네이션 포함
- 비 admin이 감사 로그 조회 → 403
- action 필터: `?action=LOGIN` → LOGIN 액션만 반환
- resource_type 필터: `?resource_type=Meeting` → Meeting 관련만 반환
- date_from/date_to 필터: 해당 기간 범위만 반환
- admin이 직원 권한 변경 → is_room_manager=True → EmployeeHistory(UPDATE) 기록
- 비 admin이 권한 변경 → 403

## Acceptance Criteria

```bash
cd backend
uv run pytest tests/test_admin.py -v
uv run ruff check app/routers/admin.py app/repositories/audit_repo.py app/schemas/admin.py
```

## 검증 절차

1. 테스트 전체 통과 확인
2. 체크리스트:
   - `GET /api/admin/audit-logs` 응답에 `detail` JSONB 필드가 포함되는가?
   - AuditLog에 DELETE API가 없는가? (조회 전용)
   - 권한 변경 API가 `EmployeeResponse`를 반환하며 `password_hash`를 포함하지 않는가?
   - 감사 로그 조회가 최신순으로 정렬되는가?
3. `phases/6-admin/index.json` step 0 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "감사로그 조회 API 완성(필터/페이지네이션/단건조회). 직원권한관리 PUT API 추가. admin 라우터 완성"`

## 금지사항

- `DELETE /api/admin/audit-logs` 또는 감사 로그를 삭제하는 어떤 API도 구현 금지. 이유: 감사 로그는 불변 (PRD 핵심 규칙)
- AuditLog를 admin 라우터에서 직접 INSERT하지 마라. 이유: AuditMiddleware 또는 각 리포지토리에서 기록 (로직 분산 방지)
- 권한 변경을 `PUT /api/employees/{emp_no}` 일반 수정 엔드포인트와 합치지 마라. 이유: 권한 변경은 별도 감사 필요
