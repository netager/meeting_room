# Architecture Decision Records

## 철학

MVP 속도 최우선. 외부 의존성 최소화. 작동하는 최소 구현을 선택한다.
폐쇄망 운영 환경 기준: 외부 인터넷 없이 완전히 동작해야 한다.
모든 결정은 "단일 서버, 50명 동시 사용자, 폐쇄망"을 기준으로 최적화한다.

---

### ADR-001: FastAPI 선택 (Python 백엔드)

**결정**: Flask/Django 대신 FastAPI 사용

**이유**:
- 자동 OpenAPI 문서(Swagger UI) 생성 → 프론트-백 계약 명확화
- Pydantic 기반 타입 검증 → 요청/응답 스키마 자동 검증 및 직렬화
- async/await 기본 지원 → SQLAlchemy async와 자연스럽게 통합
- 의존성 주입 시스템 → 인증, 권한, DB 세션을 선언적으로 처리

**고려한 대안**:
- Django: Admin, ORM 배터리 포함이나 async 지원이 제한적. 우리 규모에서 오버킬
- Flask: 가볍지만 타입 검증, 문서 자동 생성을 직접 구성해야 함

**트레이드오프**: Django Admin 같은 즉시 사용 가능한 관리 UI가 없어 직접 구현해야 함

---

### ADR-002: 순수 Svelte + Vite 선택 (프론트엔드)

**결정**: SvelteKit 대신 순수 Svelte + Vite SPA 구성

**이유**:
- 폐쇄망 단일 서버: SSR 불필요, SPA로 충분
- SvelteKit의 파일 기반 라우팅·SSR·API 라우트는 사용하지 않을 기능
- Vite의 빠른 HMR과 빌드만 활용
- 빌드 결과물(dist/)을 FastAPI StaticFiles로 서빙 → 단일 Docker 이미지

**고려한 대안**:
- SvelteKit: SSR, 파일 라우팅 편리하나 Node.js 런타임 추가 필요
- React/Vue: Svelte 대비 번들 크기 크고 학습 곡선

**트레이드오프**: 라우팅을 직접 구현해야 함 (해시 기반 라우터 사용)

---

### ADR-003: PostgreSQL + SQLAlchemy 2.x (async) + Alembic

**결정**: PostgreSQL 16, SQLAlchemy 2.x async 모드, asyncpg 드라이버, Alembic 마이그레이션

**이유**:
- JSONB 타입: 이력 테이블의 before/after 데이터를 유연하게 저장
- 트랜잭션·ACID: 중복 예약 방지에 `SELECT FOR UPDATE` 필요
- asyncpg: FastAPI async와 네이티브 통합, 동기 드라이버(psycopg2) 대비 성능 우수
- Alembic: SQLAlchemy 모델에서 자동 마이그레이션 생성, 버전 관리

**고려한 대안**:
- SQLite: 폐쇄망 단일 서버이므로 가능하나, `SELECT FOR UPDATE` 미지원으로 중복 예약 방지 구현 불가
- MySQL/MariaDB: JSONB 없음, async 드라이버 생태계 미성숙

**트레이드오프**:
- sync/async 세션 혼용 불가. 배치·테스트 코드도 async로 작성해야 함
- 테스트 픽스처가 sync보다 복잡 (pytest-asyncio 필요)

---

### ADR-004: uv (Python 패키지 매니저)

**결정**: pip/virtualenv/poetry 대신 uv 사용

**이유**:
- pip 대비 10~100배 빠른 의존성 해석·설치
- `pyproject.toml` + `uv.lock`으로 재현 가능한 빌드
- `uv run`으로 venv 활성화 없이 명령 실행 (Docker 빌드 간소화)

**규칙**:
- `uv.lock` 반드시 커밋 (삭제·gitignore 금지)
- `pip install` 절대 사용 금지

**트레이드오프**: 폐쇄망 환경에서 uv를 먼저 설치해야 하나, Docker 이미지 빌드는 인터넷 환경에서 수행하므로 문제 없음

---

### ADR-005: Tailwind CSS v4

**결정**: Svelte Scoped CSS 대신 Tailwind CSS v4, `@tailwindcss/vite` 플러그인

**이유**:
- 별도 `.css` 파일 없이 컴포넌트 내에서 디자인 완결
- v4: `tailwind.config.js` 없이 CSS 변수로 커스텀 토큰 관리
- UI_GUIDE.md의 색상·타이포그래피·간격 토큰을 클래스로 직접 표현

**셋업 규칙**:
- `tailwind.config.js` 생성 금지 (v4는 불필요)
- 커스텀 토큰은 `src/app.css`의 `@theme {}` 블록에만 정의
- 컴포넌트 `<style>` 블록은 Tailwind로 표현 불가능한 keyframe 전용

---

### ADR-006: REST API (JSON) 통신 방식

**결정**: FastAPI REST 엔드포인트 + 표준 fetch API 기반 클라이언트

**이유**:
- 별도 라이브러리(tRPC, GraphQL) 없이 표준 HTTP/JSON
- FastAPI Swagger UI로 프론트-백 계약 자동 문서화
- 폐쇄망에서 추가 런타임 불필요

**트레이드오프**: 실시간 기능(채팅, 알림 push) 필요 시 WebSocket/SSE 별도 추가 필요. 현재 요구사항에는 없음

---

### ADR-007: JWT 인증 (Access + Refresh Token)

**결정**: 세션 기반 대신 JWT, Access Token(메모리) + Refresh Token(HttpOnly 쿠키)

**이유**:
- 폐쇄망에서 Redis 같은 외부 세션 스토어 없이 stateless 인증
- Access Token을 메모리에 보관 → XSS로 탈취 불가
- Refresh Token을 HttpOnly SameSite=Strict 쿠키에 → XSS·CSRF 모두 방어

**구현 세부사항**:
- AT 만료: 30분, RT 만료: 7일
- RT에 `jti` 포함, 사용 후 `used_tokens` 테이블에 기록 (1회 사용 원칙)
- 권한 변경 시 해당 직원 RT를 `revoked_tokens` 테이블에 등록하여 즉시 무효화

**트레이드오프**:
- AT 즉시 무효화 불가 (만료 30분 대기 또는 블랙리스트 테이블 필요)
- RT 블랙리스트 테이블이 커지면 주기적 정리 필요 (만료된 항목 삭제 배치)

---

### ADR-008: bcrypt 비밀번호 해싱

**결정**: bcrypt(cost factor=12) 사용. `passlib[bcrypt]` 라이브러리

**이유**:
- 단방향 해시로 원문 복구 불가
- cost=12: 2024년 기준 일반 서버에서 ~0.3초/해시 (brute force 방어)
- 업계 표준. OWASP 권장

**고려한 대안**:
- Argon2: 더 강력하지만 설치·설정 복잡도 증가. 폐쇄망 환경에서 추가 라이브러리 부담
- SHA-256: 비밀번호 해싱에 부적합 (빠른 해시는 brute force에 취약)

**비밀번호 정책**:
- 최소 8자, 영문+숫자 조합 필수
- 행번과 동일 비밀번호 설정 불가
- 연속 동일 문자 4자 이상 금지

---

### ADR-009: 비관적 잠금으로 중복 예약 방지

**결정**: 회의실 중복 예약 방지에 `SELECT FOR UPDATE` (비관적 잠금) 사용

**이유**:
- 낙관적 잠금(버전 번호 비교)은 충돌 시 클라이언트가 재시도해야 함 → UX 나쁨
- 비관적 잠금은 첫 번째 트랜잭션 커밋까지 나머지를 대기시켜 충돌을 확실히 방지
- 50명 동시 사용자 규모에서 잠금 경합이 심각한 성능 문제가 될 가능성 낮음

**구현**:
```python
# 회의실 행에 행 수준 잠금 → 동일 회의실 동시 예약 직렬화
SELECT id FROM meeting_room WHERE id = :room_id FOR UPDATE NOWAIT;
# NOWAIT: 즉시 잠금 불가 시 에러 → 409 반환 (대기 없음)
```

**고려한 대안**:
- DB Unique Constraint: 시간 구간 겹침 검사는 단순 unique constraint로 불가
- Application-level lock: 다중 프로세스·컨테이너 시 공유 불가

---

### ADR-010: 파일 업로드 — 로컬 스토리지 + Docker Volume

**결정**: S3/MinIO 대신 서버 로컬 파일시스템, Docker volume 마운트

**이유**:
- 폐쇄망에서 외부 오브젝트 스토리지 사용 불가
- MinIO 구성은 별도 컨테이너·관리 오버헤드 추가
- 단일 서버 운영이므로 파일 공유 문제 없음
- Docker volume으로 컨테이너 재시작·교체 시에도 파일 유지

**파일 보안 규칙**:
- 저장 경로: `/app/uploads/{meeting_id}/{uuid}_{sanitized_name}`
- 원본 파일명은 DB에만 보존, 디스크 저장명은 UUID prefix
- MIME 타입 이중 검사 (확장자 + python-magic)
- 다운로드: `Content-Disposition: attachment` 강제

**트레이드오프**: 다중 서버 확장 시 파일 공유 문제. 현재 단일 서버 운영이므로 허용. 확장 필요 시 NFS 마운트 또는 MinIO 도입 검토

---

### ADR-011: 사내 메시지 전송 — Mock 우선, 환경 변수 전환

**결정**: `INTERNAL_MSG_API_URL` 환경 변수 유무로 Mock/실제 전환

**이유**:
- 실제 API URL·payload 구조 미확정
- 개발 환경에서 사내 메시지 시스템 접근 불가
- 코드 분기 없이 환경 변수만으로 전환 가능하게 설계

**Mock 동작**:
- `MessageLog` 테이블에 발송 기록 저장
- 개발 환경 UI(`/dev/messages`)에서 발송 내역 확인
- `APP_ENV=development` 시 사이드바에 Dev Tools 메뉴 노출

**실제 연결 시 주의사항**:
- payload 구조가 다르면 `notification_service.py`의 `_build_payload()` 메서드만 수정
- 타임아웃: `INTERNAL_MSG_API_TIMEOUT` 환경 변수 (기본 5초)
- 재시도: 실패 시 1분 간격 최대 3회 (백그라운드 태스크)

---

### ADR-012: ETL 동기화 — 임시원장 테이블 방식

**결정**: ETL 툴이 `employee_staging` 테이블에 직접 INSERT, 배치가 동기화 수행

**이유**:
- ETL 툴과 API 연동 없이 DB 레벨에서 데이터 수신 (ETL 툴 변경 불필요)
- 배치 로직을 우리 코드에서 완전히 제어 가능
- Mock 개발 시 Admin UI로 스테이징 직접 편집 → ETL 없이 동기화 테스트

**안전 장치**:
- 스테이징이 비어 있으면 배치 실행 중단 (전원 퇴직 방지)
- 배치는 트랜잭션 단위 실행 → 실패 시 전체 롤백

**트레이드오프**: ETL 툴의 스테이징 테이블 스키마 변경 시 양쪽 동기화 필요. 스키마는 최대한 단순하게 유지

---

### ADR-013: 단일 Docker 이미지 (FastAPI + Svelte 정적 파일)

**결정**: Nginx 별도 컨테이너 없이 FastAPI가 Svelte 빌드 파일 직접 서빙

**이유**:
- 폐쇄망 배포 시 이미지 수 최소화 (전달 파일 크기, 관리 복잡성 감소)
- `docker save` 시 이미지 하나만 관리
- 50명 규모에서 Nginx 없이 uvicorn 단독으로 충분한 성능

**구현**:
```python
# main.py
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")
# html=True: SPA fallback (모든 경로에서 index.html 반환)
```

**트레이드오프**: 트래픽이 많아지면 Nginx를 리버스 프록시로 앞에 두는 것이 좋으나, 사내 규모에서는 불필요

---

### ADR-014: 해시 기반 SPA 라우팅

**결정**: History API(`/meetings`) 대신 Hash 기반 라우팅(`/#/meetings`) 사용

**이유**:
- FastAPI가 `/#/` 이후 경로를 처리하지 않으므로 별도 catch-all 라우트 불필요
- `StaticFiles(html=True)`가 `404` 발생 시 자동으로 `index.html` 반환하나, 이 방식보다 해시가 더 단순
- 폐쇄망 환경에서 URL 북마크보다 앱 내 네비게이션이 주된 사용 패턴

**트레이드오프**: URL이 `/#/meetings`처럼 생김. SEO 불필요(사내 시스템)하므로 무관

---

### ADR-015: APScheduler (배치 스케줄러)

**결정**: 별도 cron 컨테이너 없이 APScheduler를 FastAPI 앱 내에서 실행

**이유**:
- 별도 컨테이너·cron 설정 없이 Python 코드로 관리
- FastAPI 앱과 같은 프로세스에서 실행 → DB 세션 풀 공유
- Admin API(`POST /api/admin/sync/run`)로 즉시 수동 실행 가능

**구현**:
- `AsyncIOScheduler` 사용 (FastAPI의 async 이벤트 루프와 통합)
- 타임존: `Asia/Seoul`
- 기본 스케줄: 매일 02:00 KST (환경 변수 `SYNC_CRON`으로 변경 가능)

**고려한 대안**:
- Celery: 메시지 브로커(Redis) 필요 → 폐쇄망 추가 의존성
- cron + docker: 별도 컨테이너 관리 및 DB 접근 설정 필요

**트레이드오프**: 앱이 재시작되면 스케줄도 재설정됨 (stateless). 실행 이력은 AuditLog로 확인

---

### ADR-016: 감사 로그 — 전용 테이블, 삭제 API 없음

**결정**: `audit_log` 테이블을 별도로 두고, 어떤 계정도 DELETE API 제공하지 않음

**이유**:
- 보안·감사 요구사항: 모든 행위 기록 보존 의무
- 애플리케이션 레벨에서 삭제 불가 → DB 직접 접근으로만 가능 (물리적 보안)

**AuditLog 별도 DB 세션 사용**:
- 메인 트랜잭션 롤백 시에도 감사 로그는 기록 유지
- 감사 로그 INSERT 실패가 메인 응답을 실패시키지 않음 (best-effort)

**장기 운영 고려**:
- 6개월 이상 운영 시 `created_at` 기준 파티셔닝 또는 아카이빙 검토
- 현재 50명 규모에서 연간 감사 로그 수백만 건 이하 → 파티셔닝 불필요
- `(actor, created_at)`, `(target_table, target_id)` 인덱스로 조회 성능 확보

---

### ADR-017: 구조화 로깅 (structlog)

**결정**: `logging` 표준 라이브러리 대신 `structlog` 사용

**이유**:
- JSON 구조화 로그 출력 → `docker logs` 또는 log aggregator에서 파싱 용이
- 요청 ID, 사용자 정보를 컨텍스트 변수로 자동 포함
- 개발 환경: 컬러·가독성 좋은 콘솔 출력, 운영: JSON 출력

**고려한 대안**:
- `logging`: 기본이나 구조화 로그를 위해 포맷터 설정이 복잡
- Loguru: 편리하나 structlog보다 커뮤니티 생태계 작음

**로그 레벨 정책**:
- `DEBUG`: 개발 환경, SQL 쿼리 포함 (echo=True)
- `INFO`: 운영 환경, 요청 처리 결과
- `WARNING`: 예상된 오류 (인증 실패, 중복 예약 등)
- `ERROR`: 예상치 못한 오류, 스택 트레이스 포함

---

### ADR-018: 타임존 — KST 단일 타임존

**결정**: 서버, DB, 모든 로그, 사용자 입력 모두 KST(Asia/Seoul, UTC+9) 기준

**이유**:
- 사내 시스템. 모든 사용자가 동일 타임존 사용
- UTC 변환 없이 직관적 개발·운영
- DB의 `TIMESTAMP` 컬럼: KST 기준 저장 (UTC 변환 없음)

**구현**:
- APScheduler 타임존: `Asia/Seoul`
- 회의 일자·시간: 사용자 입력 그대로 저장 (타임존 변환 없음)
- 폐쇄망 서버의 시스템 타임존: `Asia/Seoul` 설정 필요 (운영 체크리스트)

**트레이드오프**: 다국적 사용자 지원 불가. 사내 시스템이므로 허용

---

### ADR-019: API 버저닝 — 미적용 (단일 버전)

**결정**: `/api/v1/` 등의 버전 prefix 없이 `/api/` 사용

**이유**:
- 사내 시스템. 클라이언트(Svelte 앱)와 서버를 동시 배포
- 하위 호환성 유지 필요 없음 (외부 공개 API 아님)
- 버전 prefix는 불필요한 복잡성 추가

**트레이드오프**: 향후 외부 연동 API 제공 시 버저닝 필요. 그 시점에 `/api/v2/` 추가

---

### ADR-020: 프론트엔드 폼 유효성 검사 — 클라이언트 + 서버 이중 검사

**결정**: 클라이언트에서 즉각적 피드백, 서버에서 최종 권위 검사

**이유**:
- 클라이언트 검사만: 서버 우회 공격 취약
- 서버 검사만: UX 나쁨 (제출 후에야 오류 확인)
- 이중 검사: 빠른 피드백 + 보안 모두 확보

**클라이언트 검사 대상** (즉각 피드백):
- 필수 필드 미입력
- 시작 < 종료 시간
- 파일 크기·확장자 (서버 요청 전 차단)
- 비밀번호 정책 (실시간 ✓/✗ 표시)
- 메시지 최대 길이

**서버 검사 대상** (최종 권위):
- 회의실 중복 예약 (다른 사용자의 동시 예약 감지)
- 행번 존재 여부
- 권한 검증
- 비즈니스 규칙 (퇴직 직원 선택 방지 등)

**클라이언트 검사 구현 원칙**:
- blur(포커스 이탈) 이벤트에서 개별 필드 검사
- 폼 제출 시 전체 재검사
- 제출 버튼은 항상 활성화 (disabled 처리 금지 — UX 안티패턴)

---

### ADR-022: Silent Refresh — AT 메모리, RT HttpOnly 쿠키

**결정**: Access Token은 JS 메모리(Svelte store)에, Refresh Token은 HttpOnly SameSite=Strict 쿠키에 저장

**이유**:
- AT를 localStorage에 저장하면 XSS로 탈취 가능
- AT를 쿠키에 저장하면 CSRF 공격 노출
- 메모리 저장 + HttpOnly RT 쿠키: XSS와 CSRF 모두 방어

**페이지 새로고침 처리**:
- 새로고침 시 메모리의 AT 소멸 → 앱 초기화 시 자동으로 `/api/auth/token/refresh` 호출
- RT가 유효하면 AT 재발급 후 정상 사용
- RT도 만료면 로그인 페이지 이동

**동시 요청 갱신 경합 처리**:
- AT 만료 시 여러 요청이 동시에 401 받으면 → 첫 번째 요청만 RT로 갱신, 나머지는 갱신 완료 후 재시도 (pendingRequests 대기열)
- RT 1회 사용 원칙(jti 블랙리스트)으로 서버 측에서도 중복 갱신 방지

---

### ADR-023: 파일 업로드 진행률 — XMLHttpRequest (fetch 미사용)

**결정**: 파일 업로드에만 XMLHttpRequest 사용 (나머지는 fetch)

**이유**:
- `fetch` API는 업로드 진행률(`upload.onprogress`) 이벤트 미지원
- XHR은 `xhr.upload.addEventListener('progress', ...)` 지원
- 50MB 파일 업로드는 수십 초 소요 → 진행률 없으면 UX 매우 나쁨

**구현 범위**:
- 파일 업로드만 XHR 사용
- 인증 헤더(`Authorization: Bearer`)는 동일하게 추가
- 에러 처리는 fetch 래퍼와 동일한 ApiError 형식으로 통일

---

### ADR-024: 회의실 가용성 확인 — 타임라인 뷰 (폼 우측 패널)

**결정**: 회의 생성/수정 폼 우측에 해당 날짜·회의실의 시간대별 예약 현황 패널 표시

**이유**:
- 사용자가 "어느 시간대가 비어 있는지"를 직관적으로 확인하지 못하면 중복 예약 시도 반복 → 나쁜 UX
- 충돌 에러가 발생하면 어떤 회의와 충돌하는지 알아야 대안 선택 가능
- 예약 가능 여부를 제출 전에 사전 확인 가능 → 불필요한 서버 왕복 감소

**구현**:
- 날짜 또는 회의실 선택 시 `GET /api/meeting-rooms/{id}/schedule?date=YYYY-MM-DD` 자동 호출
- 09:00~18:00 타임라인 (시간 블록 단위 30분)
- 예약된 구간: 불투명 블록 + hover 시 회의명 툴팁
- 현재 입력 중인 시간 구간: 파란색 반투명 오버레이
- 충돌 구간(이미 예약된 시간): 빨간색 강조

---

### ADR-025: 계정 잠금 — DB 테이블 (Redis 미사용)

**결정**: 로그인 실패 횟수·잠금 시각을 `Employee` 테이블의 컬럼으로 관리

**이유**:
- 폐쇄망에서 Redis 추가 불필요
- 50명 규모에서 DB 기반으로 충분한 성능
- 잠금 상태가 영속적 (앱 재시작 후에도 유지)

**구현**:
- `login_fail_count: int`, `locked_until: datetime | null` 컬럼 추가
- 잠금 해제: 30분 경과 후 자동 해제 (별도 배치 없음, 로그인 시도 시점에 확인)

**트레이드오프**: 공격적인 분산 brute force 방어는 불가. 사내 시스템 수준의 보안으로 충분
