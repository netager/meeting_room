# Step 4: meeting-detail-ui

## 읽어야 할 파일

먼저 아래 파일들을 읽고 회의 상세 UI 설계를 파악하라:

- `/docs/PRD.md` — 섹션 5 "회의" (상태 전이, 수정 권한, 완료 처리), 섹션 6 "파일 첨부", 섹션 10 "화면 설계" (회의 상세 페이지)
- `/docs/UI_GUIDE.md` — 상태 배지, 버튼 패턴, 확인 모달 문구
- `phases/4-meeting/index.json` — step 0~3 summary
- `frontend/src/lib/api/meetings.js` — 사용 가능한 API 함수 목록
- `frontend/src/lib/components/common/` — Modal, Badge, SlidePanel 등

## 작업

### 목표
회의 상세 페이지를 구현한다. 참석자 목록, 첨부파일 목록(다운로드), 회의 취소/완료 액션, 수정 이동 버튼을 포함한다.

### `frontend/src/pages/MeetingDetail.svelte`

`/#/meetings/{id}` 라우트. props: `meetingId`.

**레이아웃:**

```
[← 목록으로]                               [수정] [취소] (주최자/admin)
                                                   [완료 처리] (admin만)

제목: 주간 개발팀 회의
상태: [예정중]
──────────────────────────────────────────
회의실:   서울 본사 3층 대회의실
날짜:     2026-05-30 (토)
시간:     14:00 ~ 16:00
주최자:   홍길동 (개발1팀 · 과장)

안건:
  이번 주 개발 현황 및 다음 스프린트 계획

참석자 (4명):
  홍길동 · 개발1팀 · 과장 (주최자)
  김철수 · 개발1팀 · 대리
  이영희 · QA팀 · 사원
  박민준 · 기획팀 · 대리

첨부파일 (2개):
  📄 주간보고서.pdf (1.2MB)   [다운로드]
  📊 스프린트계획.xlsx (890KB) [다운로드]
```

**권한별 버튼 표시:**
- `[수정]` 버튼: 주최자 또는 admin이고, 상태가 SCHEDULED인 경우
  → 클릭 시 `navigateTo('#/meetings/{id}/edit')`
- `[취소]` 버튼: 주최자 또는 admin이고, 상태가 SCHEDULED인 경우
  → 클릭 시 확인 모달: "회의를 취소하면 되돌릴 수 없습니다. 취소하시겠습니까?"
  → 확인 → `cancelMeeting(id)` → 성공 시 페이지 새로고침 + "회의가 취소되었습니다." 토스트
- `[완료 처리]` 버튼: admin만, 상태가 SCHEDULED인 경우
  → 클릭 시 확인 모달: "회의를 완료 처리하시겠습니까?"
  → 확인 → `completeMeeting(id)` → 성공 시 페이지 새로고침 + "회의가 완료 처리되었습니다." 토스트
- 상태가 CANCELLED/COMPLETED인 경우: 버튼 없음, 상태 배지 표시 (회색/초록)

**파일 다운로드:**
- `[다운로드]` 클릭 → `downloadFile(meetingId, fileId)` 호출
  - AT를 Authorization 헤더에 담아 GET 요청 → Blob 응답 → Object URL 생성 → `<a download>` 클릭
  - 다운로드 중 버튼에 "다운로드 중..." 스피너 표시
- 파일 삭제 아이콘 (업로더 또는 admin만): 클릭 → 확인 모달 → `deleteFile` → 목록 갱신

**참석자 관리 (주최자 또는 admin, SCHEDULED 상태에서만):**
- [참석자 추가] 버튼 → 참석자 검색 슬라이드 패널 (MeetingForm의 참석자 선택기 로직 재사용)
  - 추가 성공 → 참석자 목록 갱신 + "참석자가 추가되었습니다." 토스트
- 각 참석자 행 우측: [×] 삭제 버튼 (주최자 제외)
  - 삭제 성공 → 목록 갱신

**로딩/에러 상태:**
- 회의 상세 로딩 중: SkeletonTable
- 회의가 없거나 접근 권한 없음: "존재하지 않는 회의이거나 접근 권한이 없습니다." 메시지 + [목록으로] 버튼

### `frontend/src/router.js` 수정 확인

이전 step(step2)에서 준비된 라우트가 실제로 연결되었는지 확인:
```javascript
'/meetings/:id': MeetingDetail,
'/meetings/:id/edit': MeetingForm,  // meetingId prop 전달
```

동적 파라미터 파싱: `#/meetings/abc123/edit`에서 `id='abc123'`을 추출하여 컴포넌트에 prop으로 전달.

## Acceptance Criteria

```bash
cd frontend
npm run build
npm run lint
```

## 검증 절차

1. `npm run build` 에러 없음
2. 체크리스트:
   - CANCELLED/COMPLETED 상태 회의에서 [수정]/[취소]/[완료 처리] 버튼이 표시되지 않는가?
   - 파일 다운로드 시 AT가 Authorization 헤더에 포함된 fetch 요청으로 처리되는가? (URL 직접 접근이 아닌 Blob 방식)
   - 주최자를 참석자 목록에서 삭제하는 [×] 버튼이 표시되지 않는가?
   - `#/meetings/{id}/edit` 라우트에서 MeetingForm이 수정 모드로 렌더링되는가?
   - 회의 취소 확인 모달의 메시지가 PRD 섹션 10에 명시된 문구와 동일한가?
3. `phases/4-meeting/index.json` step 4 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "회의 상세 UI 완성: 참석자/파일목록/취소·완료액션(권한별)/파일다운로드(Blob)/참석자추가·삭제. 동적 라우트 /:id/edit 연결"`

## 금지사항

- 파일 다운로드 URL을 `<a href="/api/meetings/{id}/files/{fid}">` 직접 링크로 처리 금지. 이유: AT 없이는 401 반환 (인증 필요 엔드포인트)
- `history.pushState/replaceState` 금지. 이유: 해시 라우팅
- `tailwind.config.js` 생성 금지. 이유: Tailwind v4
- 취소/완료 버튼을 확인 모달 없이 즉시 실행 금지. 이유: 최종 상태 변경은 되돌릴 수 없음
