# Step 1: room-frontend

## 읽어야 할 파일

먼저 아래 파일들을 읽고 회의실 UI 설계를 파악하라:

- `/docs/PRD.md` — 섹션 4 "회의실" 상태값/집기 정의, 섹션 10 "화면 설계" (회의실 목록, 가용성 패널)
- `/docs/ARCHITECTURE.md` — "프론트엔드 UX 패턴" (Timeline/가용성 패널 코드 예시), "API 엔드포인트 목록" (회의실 섹션)
- `/docs/ADR.md` — ADR-014 (해시 라우팅), ADR-024 (Timeline 뷰)
- `/docs/UI_GUIDE.md` — 색상 시스템, 상태 배지, 테이블 패턴, 빈 상태
- `phases/3-meeting-room/index.json` — step 0 summary
- `phases/2-org/index.json` — step 2 summary (공통 컴포넌트 파일 경로 확인)
- `frontend/src/router.js` — 라우터 등록 방식
- `frontend/src/lib/components/common/` — 기존 공통 컴포넌트 목록
- `backend/app/routers/meeting_rooms.py` — API 명세 확인

## 작업

### 목표
회의실 목록, 회의실 상세(집기 포함), 날짜별 가용성 타임라인, 회의실 관리(room_manager 전용 CRUD) UI를 구현한다.

### `frontend/src/lib/api/meetingRooms.js`

```javascript
export async function listRooms(params = {}) { ... }          // GET /api/meeting-rooms?status=...
export async function getRoom(roomId) { ... }                  // GET /api/meeting-rooms/{id}
export async function createRoom(data) { ... }                 // POST /api/meeting-rooms
export async function updateRoom(roomId, data) { ... }         // PUT /api/meeting-rooms/{id}
export async function deleteRoom(roomId) { ... }               // DELETE /api/meeting-rooms/{id}
export async function getRoomSchedule(roomId, date) { ... }    // GET /api/meeting-rooms/{id}/schedule?date=YYYY-MM-DD
export async function createEquipment(roomId, data) { ... }    // POST /api/meeting-rooms/{id}/equipment
export async function updateEquipment(roomId, eqId, data) { } // PUT /api/meeting-rooms/{id}/equipment/{eq_id}
export async function deleteEquipment(roomId, eqId) { ... }   // DELETE /api/meeting-rooms/{id}/equipment/{eq_id}
```

- `updateRoom`은 응답에 `{ room, warnings }` 구조가 올 수 있음. warnings 배열이 비어있지 않으면 호출자에게 그대로 반환한다.
- 모든 함수는 `client.js`의 `get/post/put/del` 래퍼를 사용한다.

### `frontend/src/pages/MeetingRooms.svelte`

회의실 목록 페이지. 두 가지 모드: **일반 사용자 모드**와 **관리 모드(room_manager/admin)**.

**공통 기능:**
- 상태 필터 탭: 전체 / 정상 / 임시폐쇄 / 폐쇄
- 회의실 카드 그리드 (3열): 이름, 위치, 부서, 상태 배지, 집기 수
- 카드 클릭 → `RoomDetailPanel` 슬라이드 패널 열기
- 빈 상태: "등록된 회의실이 없습니다."
- 로딩: SkeletonTable (카드 형태 6개)

**관리 모드 추가 기능** (`currentUser.is_room_manager || currentUser.is_admin`일 때):
- [회의실 추가] 버튼 → `RoomFormModal` 열기
- 카드 우상단에 편집 아이콘(연필) → `RoomFormModal` 수정 모드로 열기
- 카드 우상단에 삭제 아이콘 (admin만) → 확인 모달 → DELETE

### `frontend/src/lib/components/rooms/RoomDetailPanel.svelte`

오른쪽에서 슬라이드 인 되는 SlidePanel. props: `roomId`, `open`, `onClose`, `selectedDate`.

- 회의실 기본 정보 (이름, 위치, 부서, 상태 배지)
- 집기 목록 테이블 (이름, 수량, 비고)
- [예약 현황 보기] 탭 → `RoomAvailabilityPanel` 임베드

### `frontend/src/lib/components/rooms/RoomAvailabilityPanel.svelte`

PRD 섹션 10 "회의실 가용성 패널" 및 ARCHITECTURE.md "Timeline 뷰" 코드 예시를 참고하여 구현한다.

```
[< 이전]  2026-05-25 (월)  [다음 >]

 08:00 │
 09:00 │ ████████████  회의명 (홍길동)
 10:00 │ ████████████
 11:00 │
 12:00 │ ████  점심 회의
 ...
```

- 날짜 이동: [< 이전] / [다음 >] 버튼
- 시간 범위: 08:00 ~ 20:00, 30분 슬롯
- 예약된 슬롯: `bg-blue-200` 블록 + 회의 제목 표시
- 현재 시간 기준 이미 지난 슬롯: `bg-gray-100`
- 날짜 변경 시 `getRoomSchedule(roomId, date)` 호출하여 업데이트
- 해당 날짜 예약 없음: "이 날짜에 예약된 회의가 없습니다." 메시지

### `frontend/src/lib/components/rooms/RoomFormModal.svelte`

Modal 래퍼 내부에 회의실 생성/수정 폼. props: `mode`('create'|'edit'), `room`(수정 시 기존 데이터), `onSave`, `onClose`.

**필드:**
- 이름 (text, 필수, max 100)
- 위치 (text, 필수, max 200)
- 부서 (select, `/api/departments` 목록 로드)
- 상태 (select, 수정 모드에서만 표시): NORMAL / TEMP_CLOSED / CLOSED
  - CLOSED 옵션: admin만 선택 가능. room_manager가 시도하면 "관리자만 변경 가능합니다." 안내
- [저장] → `createRoom` 또는 `updateRoom` 호출
  - `updateRoom` 응답에 `warnings` 있으면 저장 완료 후 경고 Toast (warning 타입) 1개씩 표시
- [취소] → `onClose`

**집기 관리** (수정 모드에서만):
- 집기 목록 인라인 테이블 (이름, 수량, 비고, 삭제 아이콘)
- [집기 추가] 행 (인라인 폼): 이름 입력 + 수량(number, min=1) + 비고 + [추가] 버튼
  - 수량 0 입력 시 "수량은 1 이상이어야 합니다." 인라인 에러
  - 중복 이름 → API 409 응답 → "이미 등록된 집기 이름입니다." Toast

### `frontend/src/router.js` 수정

```javascript
'/rooms': MeetingRooms,    // require_active_user 가드 적용
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
   - 상태 필터 탭 클릭 시 API 파라미터 `?status=` 가 올바르게 전달되는가?
   - `RoomAvailabilityPanel`에서 날짜 변경 시 매번 API를 호출하고 이전 데이터를 지우는가?
   - `updateRoom` 응답에 warnings가 있을 때 Toast가 warning 타입으로 표시되는가?
   - admin이 아닌 room_manager가 CLOSED 상태를 선택하면 UI에서 차단되는가?
   - `RoomFormModal`의 집기 추가 시 수량 min=1 검증이 서버 전송 전에 클라이언트에서도 검사되는가?
3. `phases/3-meeting-room/index.json` step 1 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "회의실 프론트엔드 완성: 목록(상태필터/카드그리드)/상세패널/가용성타임라인/CRUD폼(집기관리/경고Toast). meetingRooms.js API 래퍼 포함"`

## 금지사항

- `tailwind.config.js` 생성 금지. 이유: Tailwind v4
- `<style>` 블록에 커스텀 CSS 클래스 정의 금지. 이유: Tailwind v4 유틸리티 클래스만
- `history.pushState/replaceState` 금지. 이유: 해시 라우팅
- 회의실 상태 CLOSED 전환을 프론트에서만 차단하지 마라. 이유: 백엔드가 권한 최종 판정 (프론트 차단은 UX용)
- `backdrop-blur`, gradient, 보라색 계열 색상 금지. 이유: UI_GUIDE.md 안티패턴
