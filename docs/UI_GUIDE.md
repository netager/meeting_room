# UI 디자인 가이드: 회의 및 회의실 관리

## 스타일링 전략
- **Tailwind CSS v4** — `@tailwindcss/vite` 플러그인, `tailwind.config.js` 없음
- 커스텀 토큰은 `src/app.css`의 `@theme {}` 블록에서 CSS 변수로 정의한다
- 컴포넌트 내 `<style>` 블록은 Tailwind로 표현할 수 없는 복잡한 keyframe/animation 전용으로만 사용한다

## 디자인 원칙
1. 도구처럼 보여야 한다. 마케팅 페이지가 아니라 매일 쓰는 업무 대시보드.
2. 다크 모드 고정. 라이트 모드 전환 불필요.
3. 정보 밀도 우선. 여백은 충분하되 장식적 공간은 없앤다.
4. 데스크톱 브라우저 기준 (최소 너비 1280px). 모바일 최적화 불필요.

## AI 슬롭 안티패턴 — 하지 마라
| 금지 사항 | 이유 |
|-----------|------|
| `backdrop-blur` | glass morphism은 AI 템플릿의 가장 흔한 징후 |
| gradient-text (배경 그라데이션 텍스트) | AI가 만든 SaaS 랜딩의 1번 특징 |
| `shadow` 글로우 애니메이션 | 네온 글로우 = AI 슬롭 |
| 보라/인디고 브랜드 색상 | "AI = 보라색" 클리셰 |
| 모든 카드에 동일한 `rounded-2xl` | 균일한 둥근 모서리는 템플릿 느낌 |
| 배경 gradient orb (`blur-3xl` 원형) | 모든 AI 랜딩 페이지에 있는 장식 |
| "Powered by AI" 배지 | 이 시스템에 AI 기능 없음 |

## 색상 시스템
`src/app.css`의 `@theme {}` 블록에 정의한다.

### 배경
| 용도 | Tailwind 클래스 | 값 |
|------|---------------|------|
| 페이지 | `bg-[#0a0a0a]` | #0a0a0a |
| 카드 / 패널 | `bg-[#141414]` | #141414 |
| 호버 / 강조 | `bg-[#1f1f1f]` | #1f1f1f |
| 입력 필드 | `bg-neutral-900` | |

### 텍스트
| 용도 | Tailwind 클래스 |
|------|----------------|
| 주 텍스트 | `text-white` |
| 본문 | `text-neutral-300` |
| 보조 | `text-neutral-400` |
| 비활성 / 힌트 | `text-neutral-500` |

### 보더
| 용도 | Tailwind 클래스 |
|------|----------------|
| 기본 보더 | `border-neutral-800` |
| 강조 보더 | `border-neutral-700` |

### 시맨틱 색상
| 용도 | Tailwind 클래스 |
|------|----------------|
| 성공 / 예정 상태 | `text-green-500` |
| 에러 / 취소 상태 | `text-red-500` |
| 경고 / 임시폐쇄 | `text-yellow-500` |
| 완료 상태 | `text-neutral-500` |
| 정보 / 중립 | `text-neutral-400` |

### 상태 배지 색상
| 상태 | 클래스 |
|------|--------|
| 예정 | `bg-green-500/10 text-green-400 border-green-500/20` |
| 완료 | `bg-neutral-800 text-neutral-400 border-neutral-700` |
| 취소 | `bg-red-500/10 text-red-400 border-red-500/20` |
| 정상 (회의실) | `bg-green-500/10 text-green-400 border-green-500/20` |
| 임시폐쇄 | `bg-yellow-500/10 text-yellow-400 border-yellow-500/20` |
| 폐쇄 | `bg-red-500/10 text-red-400 border-red-500/20` |

## 컴포넌트 패턴

### 카드
```
rounded-lg bg-[#141414] border border-neutral-800 p-6
```

### 버튼
```
Primary : rounded-lg bg-white text-black text-sm font-medium hover:bg-neutral-200 px-4 py-2 transition-colors
Ghost   : rounded-lg border border-neutral-700 text-neutral-300 text-sm hover:bg-[#1f1f1f] px-4 py-2 transition-colors
Danger  : rounded-lg bg-red-500/10 text-red-400 text-sm border border-red-500/20 hover:bg-red-500/20 px-4 py-2 transition-colors
```

### 입력 필드
```
rounded-lg bg-neutral-900 border border-neutral-800 text-white placeholder:text-neutral-500 px-4 py-3 text-sm focus:outline-none focus:border-neutral-600
```

### 배지 / 태그
```
rounded-md text-xs px-2 py-1 border (상태별 색상 조합 적용)
```

### 테이블 (원장 목록 등)
```
헤더 행  : border-b border-neutral-800 text-xs text-neutral-500 uppercase tracking-wider
데이터 행: border-b border-neutral-800/50 hover:bg-[#1f1f1f] transition-colors
```

### 사이드바 네비게이션
```
전체 너비: w-56 (고정)
배경: bg-[#0a0a0a] border-r border-neutral-800
메뉴 항목: px-3 py-2 rounded-lg text-sm text-neutral-400 hover:bg-[#1f1f1f] hover:text-white transition-colors
활성 항목: bg-[#1f1f1f] text-white
```

## 레이아웃

### 전체 페이지 구조
```
사이드바(w-56 고정) | 메인 컨텐츠 (flex-1)
                     ├── 상단 헤더 (페이지 제목 + 액션 버튼)
                     └── 컨텐츠 영역 (px-6 py-8)
```

- 메인 컨텐츠 최대 너비: `max-w-5xl` (사이드바 제외 영역 기준)
- 기본 정렬: 좌측. `text-center`는 empty state 전용
- 카드 간격: `gap-4`
- 섹션 간격: `space-y-8`

### 회의 목록 페이지
- 상단: 필터 바 (상태, 날짜 범위, 부서, 검색)
- 테이블 형식: 회의명, 일시, 회의실, 참석자 수, 상태

### 회의 상세 / 편집 페이지
- 2컬럼 레이아웃: 좌(회의 정보) + 우(참석자, 첨부파일)

### 회의실 관리 페이지
- 테이블 형식: 회의실명, 위치, 집기 수, 상태, 담당 부서
- 행 클릭 → 집기 목록 슬라이드 패널

## 타이포그래피
| 용도 | Tailwind 클래스 |
|------|----------------|
| 페이지 제목 | `text-2xl font-semibold text-white` |
| 섹션 제목 | `text-sm font-medium text-neutral-400 uppercase tracking-wider` |
| 카드 제목 | `text-sm font-medium text-white` |
| 본문 | `text-sm text-neutral-300 leading-relaxed` |
| 캡션 / 메타 | `text-xs text-neutral-500` |
| 입력 레이블 | `text-sm font-medium text-neutral-300` |

## 애니메이션
- `transition-colors duration-150` — 색상 전환 (버튼 hover 등)
- `transition-opacity duration-200` — 요소 페이드 (모달 등)
- 그 외 모든 애니메이션 금지

## 아이콘
- SVG 인라인, `stroke-width="1.5"`
- 크기: `w-4 h-4` (인라인), `w-5 h-5` (단독)
- 아이콘을 둥근 배경 박스로 감싸지 않는다

## 모달 / 다이얼로그
```
오버레이: fixed inset-0 bg-black/60
패널   : rounded-lg bg-[#141414] border border-neutral-800 p-6 max-w-lg w-full
```
- 파괴적 행위(삭제, 취소 상태 변경) 전에 반드시 확인 모달 표시
- 모달 내 버튼: 오른쪽 정렬, Primary + Ghost 조합

## 개발 환경 전용 UI
- `APP_ENV=development` 시 사이드바 하단에 "Dev Tools" 섹션 표시
- `/dev/messages` — Mock 메시지 발송 내역 목록 (수신자, 내용, 발송 시각)
- 개발 환경 UI는 프로덕션 빌드에서 렌더링하지 않는다
