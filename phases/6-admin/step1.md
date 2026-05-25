# Step 1: admin-frontend

## 읽어야 할 파일

먼저 아래 파일들을 읽고 관리자 전체 UI를 파악하라:

- `/docs/PRD.md` — 섹션 9 "감사 로그", 섹션 3 "권한 체계", 섹션 10 "화면 설계" (관리자 메뉴 완성)
- `/docs/UI_GUIDE.md` — 테이블, 필터, 배지, 빈 상태
- `phases/6-admin/index.json` — step 0 summary
- `phases/2-org/index.json` — step 2 summary (Admin.svelte 기존 구조 확인)
- `frontend/src/pages/Admin.svelte` — 기존 탭 구조 (직원관리/부서팀관리/ETL동기화)
- `frontend/src/lib/api/` — 기존 API 래퍼 목록
- `backend/app/routers/admin.py` — API 명세 확인

## 작업

### 목표
Admin.svelte에 감사 로그 탭을 추가하고, 직원 권한 관리 UI를 완성한다.

### `frontend/src/lib/api/admin.js` 추가

기존 employees.js의 `updatePermissions`는 이미 있음. 신규 추가:

```javascript
export async function getAuditLogs(params = {}) { ... }  // GET /api/admin/audit-logs
export async function getAuditLog(logId) { ... }          // GET /api/admin/audit-logs/{id}
```

### `frontend/src/pages/Admin.svelte` — 탭 4 추가: 감사 로그

기존 3개 탭(직원관리/부서팀관리/ETL동기화)에 4번째 탭 추가.

**탭 4: 감사 로그**

필터 영역:
- 액션 select: 전체 / LOGIN / CREATE / UPDATE / DELETE / BATCH_RUN
- 리소스 타입 select: 전체 / Meeting / MeetingRoom / Employee / Department / Team
- 직원 검색 input (actor_emp_no 또는 이름 — API는 emp_no 기준이므로 검색 API 활용)
- 기간: 시작일 ~ 종료일
- [검색] 버튼

테이블:

| 시각 | 액션 | 리소스 | 리소스 ID | 수행자 | IP |
|------|------|--------|-----------|--------|-----|

- 행 클릭 → `AuditLogDetailModal` 열기: `detail` JSONB를 JSON 형태로 표시
- 페이지네이션 (Pagination 컴포넌트)
- 빈 상태: "조회 조건에 맞는 감사 로그가 없습니다."
- 로딩: SkeletonTable (10행)

**`AuditLogDetailModal.svelte`:**
- Modal 컴포넌트 재사용
- `detail` 객체를 `<pre>` 태그로 JSON.stringify(detail, null, 2) 표시
- 폰트: monospace

### `frontend/src/pages/Admin.svelte` — 탭 1 직원 권한 토글 완성

step 2-2에서 기본 구조를 만들었으나 권한 토글 기능이 완성되지 않았을 수 있음. 확인 후 필요시 완성:

- 직원 상세 SlidePanel에서 is_admin / is_room_manager 스위치 토글
- 토글 변경 → 확인 모달: "홍길동의 관리자 권한을 [부여/해제]하시겠습니까?"
- 확인 → `updatePermissions(empNo, { is_admin, is_room_manager })` 호출
- 성공 → "권한이 변경되었습니다." 토스트 + 직원 정보 갱신
- 본인 권한 변경 시: "자신의 권한은 변경할 수 없습니다." 에러 Toast (서버도 403 반환)

### `frontend/src/lib/components/common/JsonViewer.svelte` (선택적 추가)

```svelte
<!-- props: data (object), 단순 <pre> 래퍼 -->
<pre class="text-xs font-mono bg-gray-50 p-4 rounded overflow-auto max-h-96 whitespace-pre-wrap">
  {JSON.stringify(data, null, 2)}
</pre>
```

## Acceptance Criteria

```bash
cd frontend
npm run build
npm run lint
```

## 검증 절차

1. `npm run build` 에러 없음
2. 체크리스트:
   - 감사 로그 탭이 4번째로 추가되고 기존 탭이 깨지지 않는가?
   - 감사 로그 행 클릭 시 detail JSONB가 Modal에 JSON 포맷으로 표시되는가?
   - 직원 권한 토글 시 확인 모달이 표시되는가? ("부여" vs "해제" 문구가 현재 상태에 따라 올바르게 표시되는가?)
   - 본인 권한 변경 시도 시 서버 403 에러가 Toast로 표시되는가?
   - 감사 로그 필터 변경 시 page=1로 리셋되는가?
3. `phases/6-admin/index.json` step 1 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "관리자 UI 완성: 감사로그 탭(필터/테이블/상세JSONB모달) 추가. 직원 권한 토글(확인모달/본인변경차단) 완성. Admin.svelte 4탭 구조 완성"`

## 금지사항

- `tailwind.config.js` 생성 금지. 이유: Tailwind v4
- `<style>` 블록에 커스텀 CSS 클래스 정의 금지. 이유: Tailwind v4 유틸리티 클래스만
- 감사 로그 삭제 버튼이나 수정 UI 구현 금지. 이유: 감사 로그는 불변 (PRD 핵심 규칙)
- 본인 권한 변경을 프론트에서만 차단하지 마라. 이유: 백엔드 403 응답을 Toast로 처리해야 함 (프론트 차단은 UX용)
- `backdrop-blur`, gradient, 보라색 계열 색상 금지. 이유: UI_GUIDE.md 안티패턴
