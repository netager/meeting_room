# Step 1: notification-frontend

## 읽어야 할 파일

먼저 아래 파일들을 읽고 알림 UI 설계를 파악하라:

- `/docs/PRD.md` — 섹션 7 "내부 메시지 알림", 섹션 10 "화면 설계" (알림 패널 UX)
- `/docs/UI_GUIDE.md` — 색상 시스템, 배지, 드롭다운 패턴
- `phases/5-notification/index.json` — step 0 summary
- `frontend/src/lib/components/layout/AppShell.svelte` — 상단바 구조 확인
- `frontend/src/lib/components/common/` — Pagination 등 공통 컴포넌트

## 작업

### 목표
AppShell 상단바에 알림 벨 아이콘(미확인 뱃지)과 클릭 시 알림 드롭다운 패널을 구현한다.

### `frontend/src/lib/api/notifications.js`

```javascript
export async function getNotifications(params = {}) { ... } // GET /api/notifications?page&size
```

### `frontend/src/lib/stores/notifications.js`

```javascript
export const unreadCount = writable(0)
export const notifications = writable([])

export async function fetchNotifications(page = 1) {
    // GET /api/notifications 호출 → notifications 업데이트
}

export async function pollNotifications() {
    // 30초마다 fetchNotifications() 호출 (setInterval)
    // 앱 마운트 시 시작, 언마운트 시 clearInterval
}
```

- `unreadCount`: `status === 'SENT'` 인 알림 건수 (서버가 읽음 처리 API를 제공하지 않으므로 프론트에서 세션 단위 관리)
  - 페이지 열 때 현재 `notifications` 배열 크기를 기준으로 설정
  - 드롭다운 열면 `unreadCount = 0`으로 리셋

### `frontend/src/lib/components/layout/NotificationBell.svelte`

AppShell 상단바 우측에 배치할 알림 벨 컴포넌트.

```
🔔 [3]     ← 벨 아이콘 + 뱃지 (unreadCount > 0 일 때)
     ↓ 클릭
┌─────────────────────────────────┐
│ 알림                             │
├─────────────────────────────────┤
│ [회의 신청] 주간 개발팀 회의       │
│ 2026-05-30 14:00~16:00          │
│ 서울 본사 3층 대회의실            │
│                    5분 전        │
├─────────────────────────────────┤
│ [회의 취소] 월간 기획회의          │
│ 2026-05-28 | 취소 처리되었습니다. │
│                    2시간 전       │
├─────────────────────────────────┤
│ [더 보기 →]                      │
└─────────────────────────────────┘
```

**동작:**
- 드롭다운 오픈 시 `unreadCount = 0` 리셋
- 상대 시간 표시: "방금 전", "N분 전", "N시간 전", "N일 전"
- 최대 5개 미리보기, [더 보기] 클릭 → `navigateTo('#/notifications')`
- 드롭다운 외부 클릭 시 닫기

**상태별 스타일:**
- SENT: 일반 배경 (`bg-white`)
- PENDING/SENDING: 흐릿하게 (`opacity-60`)
- FAILED: 붉은 테두리 또는 아이콘

### `frontend/src/pages/Notifications.svelte`

`/#/notifications` 라우트. 전체 알림 목록 페이지.

- 테이블: 이벤트 타입 배지, 메시지, 상태, 수신 시각
- 페이지네이션 (Pagination 컴포넌트)
- 빈 상태: "알림이 없습니다."
- 이벤트 타입 배지:
  - CREATED: `bg-blue-100 text-blue-700`
  - UPDATED: `bg-yellow-100 text-yellow-700`
  - CANCELLED: `bg-gray-100 text-gray-600`
  - COMPLETED: `bg-green-100 text-green-700`

### `frontend/src/lib/components/layout/AppShell.svelte` 수정

상단바 우측에 `NotificationBell` 컴포넌트 추가:

```svelte
<header class="h-14 border-b flex items-center justify-between px-6">
  <h1 class="text-lg font-semibold">{페이지 제목}</h1>
  <div class="flex items-center gap-4">
    <NotificationBell />
    <span class="text-sm text-gray-600">{currentUser.name}</span>
  </div>
</header>
```

### `frontend/src/router.js` 수정

```javascript
'/notifications': Notifications,
```

### `frontend/src/App.svelte` 수정

앱 마운트 시 알림 폴링 시작:

```javascript
onMount(async () => {
  await initAuth()
  if ($isAuthenticated) {
    pollNotifications()
  }
})
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
   - 30초마다 알림 API가 호출되는가? (Network 탭에서 확인)
   - 드롭다운 열기 → unreadCount가 0으로 리셋되는가?
   - 드롭다운 외부 클릭 시 닫히는가?
   - 상대 시간 표시가 올바른가? (created_at 기준)
   - `/#/notifications` 페이지에서 페이지네이션이 동작하는가?
3. `phases/5-notification/index.json` step 1 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "알림 프론트엔드 완성: NotificationBell(30초 폴링/unread뱃지/드롭다운5개미리보기)/Notifications 전체 목록 페이지/AppShell 상단바 통합"`

## 금지사항

- `tailwind.config.js` 생성 금지. 이유: Tailwind v4
- `<style>` 블록에 커스텀 CSS 클래스 정의 금지. 이유: Tailwind v4 유틸리티 클래스만
- `history.pushState/replaceState` 금지. 이유: 해시 라우팅
- 알림 폴링 interval을 `clearInterval` 없이 등록 금지. 이유: 컴포넌트 언마운트 시 메모리 누수
- WebSocket 또는 SSE 구현 금지. 이유: 현재 스펙은 폴링 방식 (ADR에 명시된 범위)
