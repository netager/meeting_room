# Step 1: auth-frontend

## 읽어야 할 파일

먼저 아래 파일들을 읽고 UI 및 인증 설계를 파악하라:

- `/docs/PRD.md` — 섹션 10 "화면 설계": 로그인 폼, 비밀번호 변경 페이지, 계정 잠금 UI, 세션 만료 UX, 네비게이션 구조(사이드바)
- `/docs/ARCHITECTURE.md` — "SPA 라우팅", "프론트엔드 UX 패턴" 전체 (Silent Refresh, Toast, fetch 래퍼)
- `/docs/ADR.md` — ADR-014 (해시 기반 SPA 라우팅), ADR-022 (Silent Refresh)
- `/docs/UI_GUIDE.md` — 색상 시스템, 버튼/입력 패턴, 타이포그래피
- `phases/1-auth/index.json` — step 0 summary 확인
- `backend/app/routers/auth.py` — API 엔드포인트 명세 확인

## 작업

### 목표
로그인 페이지, 비밀번호 강제 변경 페이지, fetch 래퍼(Silent Refresh 포함), 전역 Toast 시스템, SPA 라우터, AppShell(사이드바)을 구현한다.

### `frontend/src/lib/api/client.js`

ARCHITECTURE.md의 "fetch 래퍼 — 토큰 자동 갱신" 패턴을 그대로 구현한다:

```javascript
// 핵심 시그니처
export async function request(path, options = {}) { ... }
export async function get(path, options = {}) { return request(path, { method: 'GET', ...options }) }
export async function post(path, body, options = {}) { ... }
export async function put(path, body, options = {}) { ... }
export async function patch(path, body, options = {}) { ... }
export async function del(path, options = {}) { ... }
export class ApiError extends Error { constructor(code, message, detail, status) { ... } }
export function getAccessToken() { ... }
export function setAccessToken(token) { ... }  // auth store에 저장
export function clearAccessToken() { ... }
```

- 동시 401 요청이 여러 개일 때 RT 갱신은 1번만 (pendingRequests 대기열 패턴)
- `X-Request-ID` 헤더 모든 요청에 추가 (crypto.randomUUID())
- 갱신 실패 시 `navigateTo('#/login')` + `showToast('세션이 만료되었습니다.', 'error')`

### `frontend/src/lib/api/auth.js`

```javascript
export async function login(username, password) { ... }   // POST /api/auth/login
export async function logout() { ... }                     // POST /api/auth/logout
export async function refreshToken() { ... }               // POST /api/auth/token/refresh
export async function changePassword(currentPw, newPw) { ... }  // POST /api/auth/password/change
```

### `frontend/src/lib/stores/auth.js`

```javascript
export const currentUser = writable(null)       // { emp_no, name, is_admin, is_room_manager, is_initial_password }
export const isAuthenticated = derived(currentUser, $u => $u !== null)
export const isInitialPassword = derived(currentUser, $u => $u?.is_initial_password ?? false)

export async function initAuth() {
  // 앱 초기화 시 호출. RT 쿠키로 AT 재발급 시도
  // 성공: currentUser 설정
  // 실패: currentUser = null (로그인 페이지로)
}
```

### `frontend/src/lib/stores/toast.js`

ARCHITECTURE.md "Toast 시스템" 코드를 그대로 구현한다:
- `showToast(message, type, duration)` — success/error/warning/info
- 최대 3개, warning은 duration=0 (수동 닫기 필수)

### `frontend/src/router.js`

해시 기반 SPA 라우터:

```javascript
// 라우트 정의
const routes = {
  '/login': Login,
  '/password-change': PasswordChange,
  '/': Dashboard,           // 내 회의 (로그인 필요)
  '/meetings': MeetingList,
  // ... 이후 Phase에서 추가
}

export const currentRoute = writable('/login')
export function navigateTo(hash) { window.location.hash = hash }

// window.hashchange 이벤트 감지 → currentRoute 업데이트
// 인증 가드: 로그인 필요 라우트에서 비인증 시 #/login으로 이동
// is_initial_password=true이면 #/password-change 이외 접근 차단
```

### `frontend/src/pages/Login.svelte`

PRD 섹션 10의 로그인 UX를 구현한다:

- 행번(6자리) + 비밀번호 입력 폼
- 엔터키로 제출
- 에러 표시: 폼 상단 인라인 메시지 (빨간색 텍스트)
- 잠금 상태(423): "계정이 잠겼습니다. 잠금 해제까지: {분}:{초}" 카운트다운 표시
- 제출 중 버튼 비활성화 + 텍스트 "로그인 중..."
- 로그인 성공 + is_initial_password=true → `#/password-change`
- 로그인 성공 + is_initial_password=false → `#/` (내 회의)

### `frontend/src/pages/PasswordChange.svelte`

PRD 섹션 10의 최초 로그인 비밀번호 변경 페이지:

- 현재 비밀번호, 새 비밀번호, 새 비밀번호 확인 입력
- 비밀번호 정책 실시간 ✓/✗ 표시 (8자 이상, 영문 포함, 숫자 포함)
- 새 비밀번호 ≠ 확인 입력 시 인라인 에러
- 변경 성공 → `#/` + "비밀번호가 변경되었습니다." 토스트
- 최초 로그인 강제 상태에서는 사이드바 없음 (단독 페이지)

### `frontend/src/lib/components/layout/AppShell.svelte`

```svelte
<!-- 전체 레이아웃: 사이드바(w-56) + 메인 영역(flex-1) -->
<!-- 사이드바 구조는 PRD 섹션 10 "네비게이션 구조" 정의 그대로 -->
<!-- 권한에 따라 메뉴 항목 조건부 표시: is_admin, is_room_manager -->
<!-- 하단: 현재 사용자 이름+행번, 로그아웃 버튼 -->
```

### `frontend/src/lib/components/common/Toast.svelte`

```svelte
<!-- $toasts store를 구독하여 우측 하단에 스택 렌더링 -->
<!-- 타입별 색상: success=green-500/10, error=red-500/10, warning=yellow-500/10 -->
<!-- 닫기 버튼, 자동 사라짐 -->
```

### `frontend/src/main.js`

```javascript
import './app.css'
import App from './App.svelte'

const app = new App({ target: document.getElementById('app') })
export default app
```

### `frontend/src/App.svelte`

```svelte
<script>
  import { onMount } from 'svelte'
  import { initAuth, isAuthenticated, isInitialPassword } from './lib/stores/auth.js'
  import { currentRoute } from './router.js'
  import Toast from './lib/components/common/Toast.svelte'
  import AppShell from './lib/components/layout/AppShell.svelte'
  // 라우트별 페이지 컴포넌트 import

  onMount(async () => {
    await initAuth()
    // 해시 기반 초기 라우트 설정
  })
</script>

<Toast />
{#if 인증이 필요 없는 라우트}
  <!-- Login, PasswordChange -->
{:else}
  <AppShell>
    <!-- 현재 라우트에 맞는 페이지 컴포넌트 -->
  </AppShell>
{/if}
```

## Acceptance Criteria

```bash
# 프론트엔드 빌드 오류 없음
cd frontend && npm run build

# 린트
npm run lint

# 백엔드와 함께 수동 E2E 확인
# 1. backend 실행: cd backend && uv run uvicorn app.main:app --reload
# 2. frontend 실행: cd frontend && npm run dev
# 3. 브라우저에서 http://localhost:5173 → 로그인 페이지 표시 확인
# 4. admin / admin123 로그인 → 비밀번호 변경 페이지 이동 확인
# 5. 비밀번호 변경 → 내 회의 페이지(대시보드) 이동 확인
# 6. 잘못된 비밀번호 → 에러 메시지 표시 확인
```

## 검증 절차

1. `npm run build` 에러 없이 완료 확인
2. 체크리스트:
   - AT가 응답 body에서만 추출되고, 쿠키나 localStorage에 저장되지 않는가?
   - 동시 401 발생 시 RT 갱신 요청이 1번만 가는가? (pendingRequests 배열 확인)
   - `#/password-change` 상태에서 사이드바가 보이지 않는가?
   - 비밀번호 정책이 입력 중 실시간으로 ✓/✗ 토글되는가?
   - `window.location.hash`로만 라우팅하고 History API push/replace를 쓰지 않는가?
3. `phases/1-auth/index.json` step 1 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "인증 프론트엔드 완성: fetch래퍼(SilentRefresh+pendingQueue)/auth store/Toast 시스템/해시 라우터/Login.svelte/PasswordChange.svelte/AppShell.svelte"`
   - 실패 3회 → `"status": "error"`, `"error_message": "구체적 에러"`

## 금지사항

- `localStorage.setItem('token', ...)` 금지. 이유: XSS 탈취 위험. AT는 메모리(store)에만
- `history.pushState` / `history.replaceState` 금지. 이유: 해시 라우팅으로 통일 (ADR-014)
- `tailwind.config.js` 생성 금지
- `<style>` 블록에 커스텀 클래스 정의 금지. 이유: Tailwind v4 유틸리티 클래스만 사용
- 기존 테스트 파일 수정 금지
