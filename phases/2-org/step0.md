# Step 0: org-backend

## 읽어야 할 파일

먼저 아래 파일들을 읽고 조직·직원 도메인을 파악하라:

- `/docs/PRD.md` — 섹션 1 "조직 구조", 섹션 3 "인증 및 권한" (권한 체계, 권한 부여 규칙), 섹션 8 "페이지네이션 및 검색"
- `/docs/ARCHITECTURE.md` — "API 엔드포인트 목록" (직원/부서/팀), "이력 기록 패턴", "에러 응답 형식"
- `phases/0-foundation/index.json` — step 0~2 summary
- `phases/1-auth/index.json` — step 0 summary
- `backend/app/models/org.py` — Department, Team, Employee, EmployeeStaging, *History 모델
- `backend/app/dependencies.py` — require_admin, require_active_user
- `backend/app/config.py` — settings

## 작업

### 목표
부서, 팀, 직원원장의 CRUD API와 Repository를 구현한다. 각 CRUD마다 이력 테이블에 변경 기록을 남긴다.

### `backend/app/repositories/org_repo.py`

```python
# Department
async def get_departments(db, include_inactive=False) -> list[Department]
async def get_department(dept_code: str, db) -> Department | None
async def create_department(data: dict, changed_by: str, db) -> Department
    # INSERT department + DepartmentHistory(CREATE) — 동일 트랜잭션
async def update_department(dept_code: str, data: dict, changed_by: str, db) -> Department
    # UPDATE + DepartmentHistory(UPDATE, before/after JSON)
async def delete_department(dept_code: str, changed_by: str, db) -> None
    # 소속 팀 또는 직원이 있으면 HTTPException 409 CONFLICT
    # DELETE + DepartmentHistory(DELETE)

# Team (동일 패턴)
async def get_teams(dept_code: str, db) -> list[Team]
async def get_team(team_code: str, db) -> Team | None
async def create_team(data: dict, changed_by: str, db) -> Team
async def update_team(team_code: str, data: dict, changed_by: str, db) -> Team
async def delete_team(team_code: str, changed_by: str, db) -> None
    # 소속 직원이 있으면 HTTPException 409 CONFLICT

# Employee
async def get_employees(db, page=1, size=20, status=None, search=None) -> tuple[list[Employee], int]
    # 반환: (items, total). search는 이름 부분 일치
async def get_employee(emp_no: str, db) -> Employee | None
async def update_employee(emp_no: str, data: dict, changed_by: str, db) -> Employee
    # 비밀번호·권한 필드는 이 함수로 변경 불가 (별도 함수)
async def retire_employee(emp_no: str, changed_by: str, db) -> None
    # status = RETIRED, EmployeeHistory(DELETE)
async def search_employees_for_attendee(query: str, db) -> list[Employee]
    # 재직 중인 직원만, 최대 50건, 이름+행번 부분 일치
async def update_permissions(emp_no: str, is_admin: bool, is_room_manager: bool, changed_by: str, db) -> Employee
    # 권한 변경 후 EmployeeHistory(UPDATE) 기록
```

### `backend/app/schemas/org.py`

Pydantic 요청/응답 스키마 정의:

```python
class DepartmentCreate(BaseModel): code: str; name: str
class DepartmentUpdate(BaseModel): name: str | None; status: str | None
class DepartmentResponse(BaseModel): code: str; name: str; status: str
    model_config = ConfigDict(from_attributes=True)

# TeamCreate, TeamUpdate, TeamResponse (동일 패턴, dept_code 포함)

class EmployeeResponse(BaseModel):
    emp_no: str; name: str; dept_code: str; team_code: str | None
    rank: str | None; status: str; is_admin: bool; is_room_manager: bool
    model_config = ConfigDict(from_attributes=True)

class EmployeeUpdate(BaseModel):
    name: str | None; dept_code: str | None; team_code: str | None; rank: str | None

class EmployeeSearchItem(BaseModel):
    emp_no: str; name: str; dept_code: str; dept_name: str; rank: str | None

class PaginatedResponse(BaseModel):
    items: list; total: int; page: int; size: int; pages: int
```

### `backend/app/routers/employees.py`

```python
router = APIRouter(prefix="/api/employees", tags=["employees"])

GET    /api/employees          → 목록 (admin 전용, ?page&size&status&search)
GET    /api/employees/search   → 참석자 선택용 검색 (?q=검색어, require_active_user)
GET    /api/employees/{emp_no} → 상세 (admin 전용)
PUT    /api/employees/{emp_no} → 정보 수정 (admin 전용)
DELETE /api/employees/{emp_no} → 퇴직 처리 (admin 전용)
```

### `backend/app/routers/departments.py`

```python
router = APIRouter(prefix="/api/departments", tags=["departments"])

GET    /api/departments           → 전체 목록 (require_active_user)
POST   /api/departments           → 생성 (require_admin)
PUT    /api/departments/{code}    → 수정 (require_admin)
DELETE /api/departments/{code}    → 삭제 (require_admin)
GET    /api/departments/{code}/teams → 팀 목록 (require_active_user)

POST   /api/teams                 → 팀 생성 (require_admin)
PUT    /api/teams/{code}          → 팀 수정 (require_admin)
DELETE /api/teams/{code}          → 팀 삭제 (require_admin)
```

### `backend/tests/test_org.py`

아래 시나리오를 테스트한다:

- 부서 생성 → DepartmentHistory(CREATE) 기록 확인
- 부서 삭제 시 소속 직원 있으면 409 반환
- 직원 검색: 재직 직원만, 최대 50건, 한글 이름 부분 일치
- admin이 아닌 사용자가 부서 생성 시도 → 403
- 직원 퇴직 처리 → status=RETIRED, EmployeeHistory(DELETE) 기록

### `backend/app/main.py` 수정

employees, departments 라우터 등록.

## Acceptance Criteria

```bash
cd backend
uv run pytest tests/test_org.py -v
uv run ruff check app/routers/employees.py app/routers/departments.py app/repositories/org_repo.py app/schemas/org.py
```

## 검증 절차

1. 테스트 전체 통과 확인
2. 체크리스트:
   - 부서/팀/직원 CRUD 시 `*History` 이력이 동일 트랜잭션 내에서 기록되는가?
   - `EmployeeResponse`에 `password_hash`가 포함되지 않는가?
   - `GET /api/employees` 응답에 페이지네이션(`total`, `pages`) 필드가 있는가?
   - 직원 검색(`/search`)에서 퇴직 직원이 반환되지 않는가?
3. `phases/2-org/index.json` step 0 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "부서/팀/직원 CRUD API + Repository 완성. 이력 기록 포함. 참석자 선택용 검색 API 포함"`

## 금지사항

- `EmployeeResponse`에 `password_hash`, `login_fail_count`, `locked_until` 필드 노출 금지. 이유: 보안 정보
- 직원 `DELETE` API를 실제 DB 삭제로 구현 금지. 이유: `status=RETIRED` 소프트 삭제
- 권한 변경(`is_admin`, `is_room_manager`)을 `PUT /employees/{emp_no}` 에서 처리 금지. 이유: 별도 권한 부여 API(`/admin/employees/{emp_no}/permissions`)에서만
