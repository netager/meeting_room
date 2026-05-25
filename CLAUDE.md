# 프로젝트: 회의 및 회의실 관리

## 기술 스택
- Backend: FastAPI (Python 3.12+)
- 패키지 관리: uv (pip/virtualenv 사용 금지)
- Frontend: Svelte + Vite (SPA, 순수 Svelte — SvelteKit 아님)
- CSS: Tailwind CSS v4 (@tailwindcss/vite 플러그인)
- Database: PostgreSQL + SQLAlchemy 2.x (async) + Alembic
- 인증: JWT (python-jose 또는 PyJWT)
- 파일 업로드: 서버 로컬 스토리지 (Docker volume)
- 배치 스케줄러: APScheduler (ETL 동기화)
- 테스트: pytest (backend), Vitest (frontend)
- 린트: ruff (backend), ESLint (frontend)
- 배포: Docker + docker-compose (폐쇄망 환경)

## 도메인 개요

`docs/PRD.md` 참조. 핵심 도메인:
- **직원원장**: 행번(6자리), 부서 > (팀) > 직원 계층 구조. ETL 임시원장 → 배치 동기화
- **회의실**: 부서별 담당 회의실 + 집기원장. 상태(정상/임시폐쇄/폐쇄)
- **회의 채널**: 일자+시작/종료 시간, 회의실 중복 예약 방지, 첨부파일, 상태(예정/완료/취소)
- **알림**: 변경 시 참석자 자동 알림. 사내 메시지 HTTP API (Mock 개발)
- **감사 로그**: 모든 로그인·행위·원장 CRUD 이력 기록 (삭제 불가)

## 아키텍처 규칙
- CRITICAL: 모든 API 로직은 `backend/app/routers/` 에서만 처리한다. Svelte 컴포넌트에서 직접 DB나 외부 API를 호출하지 말 것
- CRITICAL: Svelte 컴포넌트에서 외부 통신은 반드시 `frontend/src/lib/api/` 의 fetch 래퍼를 통해서만 한다
- CRITICAL: DB 접근은 반드시 `backend/app/repositories/` 를 통해서만 한다. 라우터나 서비스에서 SQLAlchemy 세션을 직접 쿼리하지 말 것
- CRITICAL: Python 패키지 설치는 반드시 `uv add <pkg>`를 사용한다. `pip install`을 절대 사용하지 말 것. venv를 직접 활성화하지 말 것
- CRITICAL: CSS는 반드시 Tailwind CSS v4 유틸리티 클래스를 사용한다. 별도 `.css` 파일에 커스텀 클래스를 작성하지 말 것. `tailwind.config.js`를 생성하지 말 것 (v4는 불필요)
- CRITICAL: 모든 원장(직원, 부서, 팀, 회의실, 집기, 회의)의 CRUD는 반드시 해당 `*History` 테이블에 변경 이력을 기록해야 한다
- CRITICAL: 모든 로그인·로그아웃·데이터 CRUD 행위는 `AuditLog` 테이블에 기록해야 한다. 감사 로그는 삭제 API를 제공하지 않는다
- 스키마 변경은 반드시 Alembic 마이그레이션 파일로 관리한다. DB를 직접 수정하지 말 것
- 컴포넌트는 `frontend/src/lib/components/` 에, 전역 상태는 `frontend/src/lib/stores/` 에 분리
- 회의실 중복 예약 방지 로직은 반드시 `meeting_service.py` 에서 처리한다. DB unique constraint만으로 처리하지 말 것 (시간 구간 겹침 검사 필요)
- 사내 메시지 전송은 반드시 `notification_service.py` 를 통해서만 호출한다. 라우터에서 직접 HTTP 요청하지 말 것
- 개발 환경 전용 기능(`/dev/*` 라우트, Dev Tools UI)은 `APP_ENV=development` 조건을 확인하고 노출한다

## 권한 체계
- `admin`: 별도 계정 (직원원장 외). 초기 비밀번호 `admin123`
- `is_admin=True` 직원: admin과 동일한 권한 (admin이 부여)
- `room_manager`: 담당 부서 회의실·집기 관리 권한 (admin이 부여)
- `employee`: 기본 권한. 소속 부서 회의 채널 수정 가능

## 핵심 비즈니스 규칙 (구현 시 반드시 확인)
- 회의실 중복 예약 방지: `SELECT FOR UPDATE` 비관적 잠금 필수. 시간 겹침 조건: `신규.시작 < 기존.종료 AND 신규.종료 > 기존.시작`. 취소 회의 제외
- 회의 상태 전이: `완료`·`취소`는 최종 상태. 되돌릴 수 없음. 완료/취소 상태에서 내용 수정 불가
- 자정 넘는 회의 불가 (23:00~01:00 등). 최소 30분, 최대 8시간
- 최초 로그인 시 비밀번호 강제 변경. 변경 전 다른 모든 API `403 FORCE_PASSWORD_CHANGE` 반환
- 로그인 5회 실패 시 30분 잠금. 퇴직 직원은 `403 ACCOUNT_DISABLED`
- ETL 배치: 스테이징이 비어 있으면 실행 중단 (전원 퇴직 방지 안전장치)
- 알림 발송 실패가 회의 저장 자체를 실패시키지 않음 (비동기 처리)
- 파일 업로드 실패 시 부분 저장 파일 즉시 삭제. 다중 파일 중 일부 실패 시 전체 롤백
- 감사 로그 INSERT는 별도 DB 세션 사용 (메인 트랜잭션과 분리, best-effort)
- 파일 다운로드는 참석자·생성 부서 직원·admin만 가능. `Content-Disposition: attachment` 강제

## 개발 프로세스
- CRITICAL: 새 기능 구현 시 반드시 테스트를 먼저 작성하고, 테스트가 통과하는 구현을 작성할 것 (TDD)
- 커밋 메시지는 conventional commits 형식을 따를 것 (feat:, fix:, docs:, refactor:)

## 환경 변수
`.env.example`을 복사해 `.env`를 만들고 값을 채운다.

| 변수 | 설명 | 예시 |
|------|------|------|
| `DATABASE_URL` | PostgreSQL 연결 문자열 | `postgresql+asyncpg://user:pass@localhost:5432/dbname` |
| `SECRET_KEY` | JWT 서명용 랜덤 시크릿 | `openssl rand -hex 32` |
| `FRONTEND_ORIGIN` | CORS 허용 출처 | `http://localhost:5173` (개발) |
| `APP_ENV` | 실행 환경 | `development` \| `production` |
| `INTERNAL_MSG_API_URL` | 사내 메시지 전송 API URL | 비워두면 Mock 모드 |
| `INTERNAL_MSG_API_TIMEOUT` | 메시지 API 타임아웃(초) | `5` |
| `UPLOAD_DIR` | 파일 업로드 저장 경로 | `/app/uploads` |
| `MAX_UPLOAD_SIZE_MB` | 단일 파일 최대 크기 | `50` |
| `ADMIN_RESET_TOKEN` | admin 비밀번호 초기화 토큰 | 임의 랜덤 문자열 |
| `DB_POOL_SIZE` | DB 커넥션 풀 크기 | `10` |
| `LOGIN_MAX_ATTEMPTS` | 로그인 최대 실패 횟수 | `5` |
| `LOGIN_LOCK_MINUTES` | 잠금 유지 시간(분) | `30` |
| `SYNC_CRON` | ETL 배치 스케줄 (cron) | `0 2 * * *` |

## 명령어

```bash
# 하네스 실행 (프로젝트 루트에서 실행)
python3 scripts/new-phase.py              # 새 phase 대화형 생성
python3 scripts/execute.py <phase-dir>    # phase 실행 (예: 0-foundation)
python3 scripts/execute.py <phase-dir> --push  # 실행 후 원격 브랜치 push

# 하네스 테스트 (프로젝트 루트에서 실행)
uv run pytest scripts/test_execute.py   # harness 자체 테스트

# 백엔드 (backend/ 에서 실행)
uv run uvicorn app.main:app --reload   # 개발 서버 (포트 8000)
uv run pytest                          # 테스트
uv run ruff check .                    # 린트
uv run ruff format .                   # 포맷

# 패키지 관리 (backend/ 디렉토리에서 실행)
uv add <package>                       # 의존성 추가
uv add --group dev <package>           # 개발 의존성 추가
uv sync                                # lockfile 기준 의존성 설치
uv lock                                # uv.lock 갱신

# DB 마이그레이션 (backend/ 디렉토리에서 실행)
uv run alembic upgrade head                             # 최신 마이그레이션 적용
uv run alembic revision --autogenerate -m "description" # 마이그레이션 파일 생성
uv run alembic downgrade -1                             # 한 단계 롤백
uv run alembic check                                    # 미적용 마이그레이션 확인

# 프론트엔드 (frontend/ 디렉토리에서 실행)
npm run dev    # 개발 서버 (포트 5173)
npm run build  # 프로덕션 빌드
npm run test   # Vitest 테스트
npm run lint   # ESLint

# Docker (프로젝트 루트에서 실행)
docker compose up -d          # 전체 스택 실행 (app + db)
docker compose down           # 중지
docker compose build          # 이미지 빌드
docker save meeting-room:latest | gzip > meeting-room.tar.gz  # 폐쇄망 전달용
```
