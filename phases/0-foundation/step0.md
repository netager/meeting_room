# Step 0: project-setup

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 기술 스택과 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md` — 디렉토리 구조, 기술 스택, Docker 배포 전략
- `/docs/ADR.md` — ADR-001~005 (FastAPI, Svelte, PostgreSQL, uv, Tailwind 선택 이유)
- `/CLAUDE.md` — 프로젝트 전반 규칙 및 명령어

## 작업

### 목표
`backend/`와 `frontend/` 두 개의 빈 프로젝트 초기 구조를 생성한다. 비즈니스 로직은 일절 작성하지 않는다.

### Backend 초기화 (`backend/` 디렉토리)

`backend/` 디렉토리에서 아래를 수행한다:

1. **`uv init`** 으로 프로젝트 초기화 후 `pyproject.toml` 의존성을 아래 기준으로 설정한다:
   - 런타임: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `python-jose[cryptography]`, `passlib[bcrypt]`, `python-multipart`, `python-magic`, `structlog`, `apscheduler`
   - 개발: `pytest`, `pytest-asyncio`, `httpx`, `ruff`

2. **디렉토리 골격** 생성 (빈 `__init__.py` 포함):
   ```
   backend/app/
   ├── routers/
   ├── schemas/
   ├── models/
   ├── repositories/
   ├── services/
   └── middleware/
   backend/tests/
   backend/uploads/          ← .gitkeep 파일만
   ```

3. **`backend/app/main.py`** — FastAPI 앱 객체만 생성, 라우터 없음:
   ```python
   app = FastAPI(title="회의 및 회의실 관리")
   ```

4. **`backend/alembic.ini`** + **`backend/alembic/env.py`** — Alembic 초기 설정. `env.py`는 `app.models`의 `Base.metadata`를 참조하도록 설정한다.

5. **`backend/tests/conftest.py`** — 빈 파일로 생성 (Step 1 이후 픽스처 추가 예정)

6. **`backend/pyproject.toml`** — ruff 설정 포함:
   ```toml
   [tool.ruff]
   line-length = 100
   [tool.pytest.ini_options]
   asyncio_mode = "auto"
   ```

### Frontend 초기화 (`frontend/` 디렉토리)

1. **`npm create vite@latest frontend -- --template svelte`** 으로 Svelte+Vite 프로젝트 생성 후:
   - `npm install @tailwindcss/vite tailwind`

2. **`frontend/vite.config.js`**:
   ```javascript
   import { defineConfig } from 'vite'
   import { svelte } from '@sveltejs/vite-plugin-svelte'
   import tailwindcss from '@tailwindcss/vite'

   export default defineConfig({
     plugins: [svelte(), tailwindcss()],
     server: { proxy: { '/api': 'http://localhost:8000' } }
   })
   ```

3. **`frontend/src/app.css`**:
   ```css
   @import "tailwindcss";
   @theme {
     --color-bg-page: #0a0a0a;
     --color-bg-card: #141414;
     --color-bg-hover: #1f1f1f;
   }
   ```

4. **`frontend/src/main.js`** — `import './app.css'` 포함

5. **디렉토리 골격** 생성 (빈 파일 포함):
   ```
   frontend/src/lib/api/
   frontend/src/lib/components/layout/
   frontend/src/lib/components/meeting/
   frontend/src/lib/components/room/
   frontend/src/lib/components/common/
   frontend/src/lib/stores/
   frontend/src/pages/
   ```

### 루트 파일

- **`.env.example`** — CLAUDE.md 환경 변수 테이블의 모든 항목 포함 (값은 예시 또는 빈 문자열)
- **`.gitignore`** — `.env`, `__pycache__`, `*.pyc`, `node_modules`, `dist`, `uploads/*`, `!uploads/.gitkeep`

## Acceptance Criteria

```bash
# Backend — 패키지 설치 및 임포트 확인
cd backend && uv sync
uv run python -c "import fastapi, sqlalchemy, alembic, jose, passlib, structlog, apscheduler; print('OK')"
uv run ruff check .

# Frontend — 빌드 성공 확인
cd frontend && npm install && npm run build
# dist/ 디렉토리 생성 확인
ls dist/index.html
```

## 검증 절차

1. 위 AC 커맨드를 순서대로 실행한다.
2. 아키텍처 체크리스트:
   - `backend/app/` 하위에 `routers/`, `schemas/`, `models/`, `repositories/`, `services/`, `middleware/` 모두 존재하는가?
   - `frontend/src/lib/` 하위에 `api/`, `components/`, `stores/` 존재하는가?
   - `vite.config.js`에 `tailwindcss` 플러그인이 등록되어 있는가?
   - `tailwind.config.js`가 생성되지 않았는가? (v4는 불필요)
3. 결과에 따라 `phases/0-foundation/index.json`의 step 0 상태를 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "backend/frontend 프로젝트 초기 구조 생성 완료. 의존성: fastapi+sqlalchemy+alembic+jose+passlib+structlog+apscheduler / svelte+vite+tailwindcss v4"`
   - 실패 3회 → `"status": "error"`, `"error_message": "구체적 에러"`

## 금지사항

- `tailwind.config.js` 생성 금지. 이유: Tailwind v4는 CSS 변수 방식 사용, config 파일 불필요
- `pip install` 사용 금지. 이유: uv 프로젝트에서 pip 사용 시 lockfile 불일치
- venv 직접 활성화 금지. 이유: `uv run`이 대신 처리함
- `frontend/src/` 의 기본 Svelte 샘플 코드(`App.svelte` 내용, `Counter.svelte` 등) 전부 삭제. 이유: 다음 step에서 실제 컴포넌트로 교체
- 비즈니스 로직 작성 금지. 이유: 이 step은 구조 생성만
