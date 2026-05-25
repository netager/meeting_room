# Step 2: meeting-list-ui

## 읽어야 할 파일

먼저 아래 파일들을 읽고 회의 목록 UI 설계를 파악하라:

- `/docs/PRD.md` — 섹션 5 "회의" 상태값 정의, 섹션 10 "화면 설계" (대시보드/내 회의, 회의 목록 페이지)
- `/docs/ARCHITECTURE.md` — "API 엔드포인트 목록" (회의 섹션), "프론트엔드 UX 패턴"
- `/docs/UI_GUIDE.md` — 상태 배지, 테이블 패턴, 빈 상태, 색상 시스템
- `phases/4-meeting/index.json` — step 0, 1 summary
- `phases/2-org/index.json` — step 2 summary (공통 컴포넌트 확인)
- `frontend/src/router.js` — 현재 라우트 등록 현황
- `frontend/src/lib/components/common/` — 사용 가능한 공통 컴포넌트 목록
- `backend/app/routers/meetings.py` — API 명세 확인

## 작업

### 목표
대시보드(내 회의 요약)와 전체 회의 목록 페이지를 구현한다. 공통 컴포넌트(Table, Pagination, Badge)를 최대한 재사용한다.

### `frontend/src/lib/api/meetings.js`

```javascript
export async function listMeetings(params = {}) { ... }  // GET /api/meetings
export async function getMyMeetings(params = {}) { ... } // GET /api/meetings?my=true
export async function getMeeting(meetingId) { ... }       // GET /api/meetings/{id}
export async function createMeeting(data) { ... }         // POST /api/meetings
export async function updateMeeting(meetingId, data) { } // PUT /api/meetings/{id}
export async function cancelMeeting(meetingId) { ... }    // DELETE /api/meetings/{id}
export async function completeMeeting(meetingId) { ... }  // POST /api/meetings/{id}/complete

export async function getFiles(meetingId) { ... }          // GET /api/meetings/{id}/files
export async function downloadFile(meetingId, fileId) { } // GET /api/meetings/{id}/files/{file_id}
export async function deleteFile(meetingId, fileId) { ... }// DELETE /api/meetings/{id}/files/{file_id}

export async function addAttendee(meetingId, empNo) { ... }       // POST /api/meetings/{id}/attendees
export async function removeAttendee(meetingId, empNo) { ... }    // DELETE /api/meetings/{id}/attendees/{emp_no}
```

- `downloadFile`은 fetch가 아닌 URL을 생성하여 `window.open` 또는 `<a download>` 방식으로 처리한다. 이유: 인증 토큰 첨부가 필요하므로 `get(path, { parseBlob: true })` 방식으로 Blob을 받아 object URL 생성 후 다운로드.
- 모든 함수는 `client.js`의 래퍼를 사용한다.

### `frontend/src/pages/Dashboard.svelte`

로그인 직후 진입하는 "내 회의" 대시보드. `/#/` 라우트.

**레이아웃:**
```
[오늘의 회의]        [이번 주 예정]       [내가 주최한 회의]
 N건                  N건                  N건
 (오늘 날짜 기준)     (이번 주)            (상태 무관 전체)

[오늘 & 다음 7일 내 예정 회의 목록]
─────────────────────────────────────
날짜  회의명        회의실    시간       상태
...
```

- `getMyMeetings({ date_from: today, status: 'SCHEDULED' })` 호출
- 날짜별 그룹핑 (오늘 / 내일 / 날짜 라벨)
- 빈 상태: "예정된 회의가 없습니다."
- 회의 행 클릭 → `navigateTo('#/meetings/{id}')`
- 로딩: SkeletonTable (5행)

### `frontend/src/pages/MeetingList.svelte`

전체 회의 목록 페이지. `/#/meetings` 라우트.

**필터 영역:**
- 상태 필터 탭: 전체 / 예정 / 완료 / 취소
- 기간 필터: 시작일 ~ 종료일 date input
- [내 회의만] 토글 스위치
- [회의 신청] 버튼 → `navigateTo('#/meetings/new')`

**테이블:**

| 날짜 | 시간 | 회의명 | 회의실 | 참석자 수 | 상태 |
|------|------|--------|--------|-----------|------|

- Badge 컴포넌트: SCHEDULED=blue, COMPLETED=green, CANCELLED=gray
- 행 클릭 → `navigateTo('#/meetings/{id}')`
- 페이지네이션 (Pagination 컴포넌트)
- 빈 상태: "조회 조건에 맞는 회의가 없습니다."
- 로딩: SkeletonTable

**필터 연동:**
- 필터 변경 시 page=1로 리셋 후 재조회
- URL 쿼리 파라미터와 별도로 Svelte 상태로만 관리 (해시 라우팅이므로 URL 파라미터 직렬화 불필요)

### `frontend/src/router.js` 수정

```javascript
'/': Dashboard,
'/meetings': MeetingList,
'/meetings/new': MeetingForm,    // step3에서 구현, 여기서는 import만 준비
'/meetings/:id': MeetingDetail,  // step4에서 구현, 여기서는 import만 준비
```

해시 라우터에서 `/meetings/:id` 형태 동적 라우트를 처리하려면:
- `window.location.hash`에서 `#/meetings/abc123` 형태를 파싱
- 정적 라우트(`/meetings/new`)를 동적 라우트(`/meetings/:id`)보다 먼저 매칭

## Acceptance Criteria

```bash
cd frontend
npm run build
npm run lint
```

## 검증 절차

1. `npm run build` 에러 없음
2. 체크리스트:
   - Dashboard가 `/#/` 라우트에 바인딩되어 있는가?
   - MeetingList의 필터 변경 시 page가 1로 리셋되는가?
   - Badge의 상태별 색상이 UI_GUIDE.md 색상 체계와 일치하는가? (SCHEDULED=blue, COMPLETED=green, CANCELLED=gray)
   - `/meetings/new` 와 `/meetings/:id`가 충돌 없이 분기되는가? (`/meetings/new`가 ID로 해석되지 않아야 함)
   - `getMyMeetings`에 `my=true` 파라미터가 올바르게 전달되는가?
3. `phases/4-meeting/index.json` step 2 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "회의 목록 UI 완성: Dashboard(내 회의 요약+7일 목록)/MeetingList(필터/테이블/페이지네이션). meetings.js API 래퍼 포함. 동적 라우트 파싱 구현"`

## 금지사항

- `history.pushState/replaceState` 금지. 이유: 해시 라우팅
- `tailwind.config.js` 생성 금지. 이유: Tailwind v4
- `<style>` 블록에 커스텀 CSS 클래스 정의 금지. 이유: Tailwind v4 유틸리티 클래스만
- 파일 다운로드를 `fetch` + `client.js`의 `get()`으로 처리 시 Content-Disposition 헤더가 처리되지 않을 수 있음 — Blob 방식으로 구현하라
