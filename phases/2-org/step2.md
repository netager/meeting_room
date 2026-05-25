# Step 2: org-admin-ui

## 읽어야 할 파일

먼저 아래 파일들을 읽고 관리자 UI 설계를 파악하라:

- `/docs/PRD.md` — 섹션 10 "네비게이션 구조", 섹션 3 "권한 체계"
- `/docs/UI_GUIDE.md` — 색상 시스템, 테이블 패턴, 버튼, 배지, 입력 필드, 빈 상태
- `phases/2-org/index.json` — step 0, 1 summary
- `phases/1-auth/index.json` — step 1 summary (AppShell, router.js 파일 경로 확인)
- `frontend/src/lib/components/layout/AppShell.svelte` — 사이드바 구조
- `frontend/src/router.js` — 라우터 등록 방식
- `backend/app/routers/employees.py`, `backend/app/routers/departments.py` — API 명세

## 작업

### 목표
관리자 전용 직원 관리, 부서·팀 관리, 직원 권한 부여, ETL 동기화 수동 실행 UI를 구현한다.

### `frontend/src/lib/api/employees.js`

```javascript
export async function listEmployees(params = {}) { ... }  // GET /api/employees
export async function searchEmployees(query) { ... }       // GET /api/employees/search?q=
export async function getEmployee(empNo) { ... }           // GET /api/employees/{emp_no}
export async function updateEmployee(empNo, data) { ... }  // PUT /api/employees/{emp_no}
export async function retireEmployee(empNo) { ... }        // DELETE /api/employees/{emp_no}
export async function updatePermissions(empNo, data) { ... } // PUT /api/admin/employees/{emp_no}/permissions
```

### `frontend/src/lib/api/departments.js`

```javascript
export async function listDepartments() { ... }
export async function createDepartment(data) { ... }
export async function updateDepartment(code, data) { ... }
export async function deleteDepartment(code) { ... }
export async function listTeams(deptCode) { ... }
export async function createTeam(data) { ... }
export async function updateTeam(code, data) { ... }
export async function deleteTeam(code) { ... }
```

### `frontend/src/pages/Admin.svelte`

admin 권한이 없으면 접근 차단 (라우터 가드). 탭 구조로 구성:

**탭 1: 직원 관리**
- 직원 목록 테이블: 행번, 이름, 부서, 팀, 직급, 상태(재직/퇴직), admin/manager 배지
- 필터: 상태(전체/재직/퇴직), 이름 검색
- 페이지네이션
- 행 클릭 → 직원 상세 슬라이드 패널:
  - 직원 정보 수정 (이름, 부서, 팀, 직급)
  - 권한 토글 (is_admin, is_room_manager) — 스위치 컴포넌트
  - 퇴직 처리 버튼 (확인 모달: "퇴직 처리하면 해당 직원은 로그인할 수 없습니다.")
- 빈 상태: "조회 조건에 맞는 직원이 없습니다."

**탭 2: 부서·팀 관리**
- 부서 목록 (아코디언 형태: 부서 → 팀 목록 펼치기)
- 부서 추가/수정/삭제 인라인
- 팀 추가/수정/삭제 인라인
- 삭제 시 확인 모달

**탭 3: ETL 동기화** (`APP_ENV === 'development'` 시만 임시원장 편집 표시)
- 마지막 동기화 결과 (AuditLog BATCH_RUN 조회)
- [동기화 즉시 실행] 버튼 → `POST /api/admin/sync/run` → 결과 토스트
- 개발 환경에서만: 임시원장 테이블 편집 (행 추가/삭제/수정, [동기화 실행] 버튼)

### `frontend/src/lib/components/common/` 추가 컴포넌트

이 step에서 공통 컴포넌트를 추가한다 (이후 모든 page에서 재사용):

- **`Table.svelte`**: 헤더 배열 + 행 배열을 받아 테이블 렌더링. 빈 상태 슬롯 포함
- **`Pagination.svelte`**: `page`, `pages`, `total`, `onPageChange` props
- **`Modal.svelte`**: `title`, `open`, `onClose` props. 기본 포커스는 닫기 버튼
- **`Badge.svelte`**: `text`, `variant`(success/error/warning/neutral) props
- **`SlidePanel.svelte`**: 우측에서 슬라이드 인/아웃되는 패널. `open` prop
- **`SkeletonTable.svelte`**: `rows` prop. animate-pulse 회색 블록

### `frontend/src/router.js` 수정

Admin 라우트 추가:
```javascript
'/admin': Admin,  // is_admin 가드 적용
```

## Acceptance Criteria

```bash
cd frontend
npm run build
npm run lint

# 수동 확인
# 1. admin 계정으로 로그인 → 사이드바에 "관리자 메뉴" 표시 확인
# 2. 직원 관리 탭 → 직원 목록 로딩 확인
# 3. 직원 행 클릭 → 슬라이드 패널 열림 확인
# 4. 동기화 탭 → [동기화 즉시 실행] 클릭 → 결과 토스트 확인
```

## 검증 절차

1. `npm run build` 에러 없음
2. 체크리스트:
   - admin이 아닌 사용자가 `#/admin`에 접근하면 `#/`로 리다이렉트되는가?
   - 공통 컴포넌트(Table, Pagination, Modal, Badge)가 `/admin`이 아닌 다른 페이지에서도 재사용 가능한 형태인가?
   - ETL 동기화 탭의 임시원장 편집 UI가 `APP_ENV === 'development'`일 때만 표시되는가?
3. `phases/2-org/index.json` step 2 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "관리자 UI 완성: 직원관리(목록/상세/권한토글/퇴직)/부서팀관리/ETL수동실행. 공통컴포넌트(Table/Pagination/Modal/Badge/SlidePanel/SkeletonTable) 구현"`

## 금지사항

- admin 권한 검사를 프론트엔드에서만 하지 마라. 이유: 백엔드 API에서도 require_admin 의존성이 적용되어야 함 (프론트 가드는 UX용)
- `<style>` 블록에 커스텀 CSS 클래스 정의 금지. 이유: Tailwind v4 유틸리티 클래스만
- `backdrop-blur`, gradient-text, 보라색 계열 색상, `rounded-2xl` 균일 사용 금지. 이유: UI_GUIDE.md AI 슬롭 안티패턴
