# Step 3: meeting-form-ui

## 읽어야 할 파일

먼저 아래 파일들을 읽고 회의 폼 UI 설계를 파악하라:

- `/docs/PRD.md` — 섹션 5 "회의" (생성/수정 규칙), 섹션 10 "화면 설계" (회의 신청 폼, 참석자 선택기, 파일 업로드 UX)
- `/docs/ARCHITECTURE.md` — "프론트엔드 UX 패턴" (attendee selector debounce, XHR 파일 업로드 progress, form dirty state)
- `/docs/ADR.md` — ADR-020 (클라이언트+서버 이중 검증), ADR-023 (XHR 업로드)
- `phases/4-meeting/index.json` — step 0~2 summary
- `frontend/src/lib/api/meetings.js` — API 함수 목록
- `frontend/src/lib/api/meetingRooms.js` — getRoomSchedule 사용
- `frontend/src/lib/components/rooms/RoomAvailabilityPanel.svelte` — 재사용
- `frontend/src/lib/components/common/` — Modal, SlidePanel 등 공통 컴포넌트

## 작업

### 목표
회의 신청/수정 폼을 구현한다. 참석자 검색 선택기(debounce), XHR 파일 업로드(progress bar), 회의실 가용성 확인 패널, 폼 dirty 상태 이탈 경고를 포함한다.

### `frontend/src/pages/MeetingForm.svelte`

`/#/meetings/new` 및 `/#/meetings/{id}/edit` 라우트에서 사용. props: `meetingId`(수정 시).

**폼 필드:**

| 필드 | 타입 | 검증 |
|------|------|------|
| 제목 | text | 필수, max 200 |
| 회의실 | select | 필수, NORMAL 상태 회의실만 선택 가능 |
| 날짜 | date input | 필수, 오늘 이후 |
| 시작 시간 | time select (30분 단위) | 필수 |
| 종료 시간 | time select (30분 단위) | 필수, 시작 시간 이후 |
| 안건 | textarea | 선택, max 2000자 |

- 회의실 선택 변경 시 가용성 패널 업데이트
- 날짜 변경 시 가용성 패널 업데이트

**회의실 가용성 패널** (오른쪽 사이드 또는 하단):
- `RoomAvailabilityPanel` 컴포넌트 재사용
- 회의실 + 날짜 모두 선택된 경우에만 표시
- 선택한 시간 범위를 패널에서 하이라이트 표시 (`bg-blue-100 border-blue-400`)

**참석자 선택기:**

ARCHITECTURE.md "attendee selector" 코드 예시를 그대로 구현한다:

```
[참석자 추가 검색: __________] (300ms debounce)
검색 결과 드롭다운:
  ○ 홍길동 · 개발팀 · 대리
  ○ 홍길순 · 인사팀 · 사원
이미 추가된 참석자:
  [홍길동 · 개발팀 · 대리  ×]
  [본인 이름 (주최자)  — 삭제 불가]
```

- `GET /api/employees/search?q={query}` 호출 (300ms debounce)
- 검색 결과 중 이미 추가된 참석자는 비활성화
- 본인(주최자)은 항상 목록에 포함, 삭제 불가
- 드롭다운 외부 클릭 시 닫기

**파일 업로드 (신규 작성 시에는 생성 후 업로드, 수정 시에는 즉시 업로드):**

ARCHITECTURE.md "XHR 파일 업로드" 코드 예시를 그대로 구현한다:

```
[파일 첨부] 버튼 → input[type=file] (multiple)
각 파일별:
  📄 보고서.pdf  (2.3MB)  [████████░░] 78%  [×]
  ✅ 발표자료.pptx (1.1MB)
에러: ❌ 실행파일.exe — 허용되지 않는 파일 형식
```

- XHR `upload.onprogress` 이벤트로 진행률 표시
- 허용 확장자 목록을 클라이언트에서도 사전 검증 (서버 검증과 병행)
- 50MB 초과 시 클라이언트에서 차단 + "파일 크기가 50MB를 초과합니다." 에러
- 업로드 완료 전 폼 제출 불가 (진행 중인 파일 있으면 [저장] 버튼 비활성화)

**Dirty 상태 / 이탈 경고:**

ARCHITECTURE.md "form dirty state + beforeunload" 패턴을 그대로 구현한다:

- 폼 필드가 하나라도 변경되면 `isDirty = true`
- `onDestroy`에서 `window.removeEventListener('beforeunload', ...)`
- 페이지 이탈(다른 라우트 이동) 시 확인 모달: "저장하지 않은 내용이 있습니다. 이 페이지를 떠나시겠습니까?"
- [저장] 성공 후 `isDirty = false`

**제출 흐름:**

- 신규: `createMeeting(data)` → 성공 시 `navigateTo('#/meetings/{new_id}')` + "회의가 신청되었습니다." 토스트
- 수정: `updateMeeting(id, data)` → 성공 시 `navigateTo('#/meetings/{id}')` + "회의가 수정되었습니다." 토스트
- 409 ROOM_BOOKING_CONFLICT → "선택한 시간에 이미 예약이 있습니다." 에러 인라인 표시 (Toast 아님)
- 그 외 에러 → Toast error 타입

## Acceptance Criteria

```bash
cd frontend
npm run build
npm run lint
```

## 검증 절차

1. `npm run build` 에러 없음
2. 체크리스트:
   - 참석자 검색이 300ms debounce로 동작하는가? (빠른 타이핑 시 API 과다 호출 없음)
   - 파일 업로드 중 [저장] 버튼이 비활성화되는가?
   - 클라이언트에서 허용되지 않는 확장자를 골라도 업로드 요청이 서버로 가지 않는가?
   - 폼 값 변경 후 다른 라우트 이동 시 이탈 경고 모달이 뜨는가?
   - 시작 시간이 종료 시간보다 늦게 선택된 경우 제출 버튼이 비활성화되거나 인라인 에러가 표시되는가?
   - 409 충돌 에러가 Toast가 아닌 폼 인라인 에러로 표시되는가?
3. `phases/4-meeting/index.json` step 3 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "회의 신청/수정 폼 완성: 회의실가용성패널/참석자선택기(debounce)/XHR파일업로드(progress)/dirty상태이탈경고/충돌에러인라인표시"`

## 금지사항

- 파일 업로드에 `fetch`를 사용하지 마라. 이유: ADR-023 — XHR만 progress 이벤트 지원
- `history.pushState/replaceState` 금지. 이유: 해시 라우팅
- `tailwind.config.js` 생성 금지. 이유: Tailwind v4
- 회의실 충돌 에러를 Toast로 표시하지 마라. 이유: 인라인 에러로 어느 필드 때문인지 명확히 안내해야 함
- 파일 크기/확장자 검사를 서버에만 맡기지 마라. 이유: ADR-020 클라이언트+서버 이중 검증
