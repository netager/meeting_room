# Step 0: docker-setup

## 읽어야 할 파일

먼저 아래 파일들을 읽고 배포 구성을 파악하라:

- `/docs/PRD.md` — 섹션 11 "배포 및 운영" (Docker 구성, 환경 변수, 볼륨)
- `/docs/ARCHITECTURE.md` — "배포 구조: Docker" (multi-stage, StaticFiles 마운트, 볼륨 마운트)
- `/docs/ADR.md` — ADR-001 (Docker 단일 컨테이너), ADR-011 (로컬 파일시스템 볼륨)
- `phases/0-foundation/index.json` — step 2 summary (main.py StaticFiles 마운트 확인)
- `backend/app/main.py` — StaticFiles 마운트 코드 확인
- `backend/app/config.py` — 모든 settings 필드 확인
- `.env.example` — 환경 변수 목록 확인
- `pyproject.toml` — Python 의존성 확인 (uv 사용)
- `frontend/package.json` — Node 버전, build 명령어 확인

## 작업

### 목표
Multi-stage Dockerfile과 docker-compose.yml을 작성한다. 단일 컨테이너에서 FastAPI가 Svelte 정적 파일과 API를 함께 서빙한다. 업로드 파일은 호스트 볼륨으로 유지한다.

### `Dockerfile` (프로젝트 루트)

```dockerfile
# Stage 1: Node build (Svelte + Vite)
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
# 결과: /app/frontend/dist/

# Stage 2: Python app
FROM python:3.12-slim AS app
WORKDIR /app

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 의존성 설치 (캐시 레이어 활용)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

# 앱 코드 복사
COPY backend/ ./

# 프론트엔드 빌드 결과 복사 (FastAPI StaticFiles용)
COPY --from=frontend-builder /app/frontend/dist ./static/

# 업로드 디렉토리 생성
RUN mkdir -p /app/uploads

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**주의:** `uv sync --frozen` 사용 — `uv.lock` 없이 실행하면 빌드 실패. `uv.lock`을 반드시 커밋에 포함시킨다.

### `docker-compose.yml` (프로젝트 루트)

```yaml
version: '3.9'

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: meetingroom
      POSTGRES_USER: meetingroom
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U meetingroom"]
      interval: 10s
      timeout: 5s
      retries: 5

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://meetingroom:${POSTGRES_PASSWORD:-changeme}@db:5432/meetingroom
      SECRET_KEY: ${SECRET_KEY}
      FRONTEND_ORIGIN: ${FRONTEND_ORIGIN:-http://localhost:8000}
      APP_ENV: ${APP_ENV:-production}
      UPLOAD_DIR: /app/uploads
      SYNC_CRON: ${SYNC_CRON:-0 2 * * *}
      INTERNAL_MSG_API_URL: ${INTERNAL_MSG_API_URL:-}
    volumes:
      - uploads_data:/app/uploads
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

volumes:
  postgres_data:
  uploads_data:
```

### `backend/app/main.py` 확인/수정

`phases/0-foundation/step2.md`에서 StaticFiles 마운트가 조건부로 구현되었어야 함. 확인 후 없으면 추가:

```python
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# API 라우터 등록 이후에:
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(static_dir):
    # SPA fallback: API가 아닌 모든 경로 → index.html 반환
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        index = os.path.join(static_dir, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)
        return {"error": "Frontend not built"}

    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
```

**주의:** SPA fallback 라우트는 모든 API 라우터 등록 이후에 추가해야 한다. 순서가 잘못되면 API 엔드포인트가 가려진다.

### `.dockerignore` (프로젝트 루트)

```
**/__pycache__/
**/*.pyc
**/.pytest_cache/
**/node_modules/
frontend/dist/
backend/.venv/
.env
.git/
phases/
docs/
scripts/
*.md
```

### `backend/alembic.ini` 확인

Docker 환경에서 마이그레이션 실행 방법 문서화 (README.md가 아닌 주석으로):

```ini
# Docker 환경에서 마이그레이션 실행:
# docker compose exec app uv run alembic upgrade head
```

### `scripts/docker-init.sh` (선택)

첫 실행 시 마이그레이션 + 초기 admin 계정 생성 자동화:

```bash
#!/bin/bash
# docker compose exec app bash scripts/docker-init.sh
set -e
uv run alembic upgrade head
echo "마이그레이션 완료"
# 초기 admin 계정이 없으면 생성 (admin/admin123, is_initial_password=True)
uv run python -c "
import asyncio
from app.db import get_db
from app.repositories.auth_repo import ensure_admin_account
asyncio.run(ensure_admin_account())
print('초기 admin 계정 확인 완료')
"
```

## Acceptance Criteria

```bash
# 프로젝트 루트에서 실행
docker compose build --no-cache
docker compose up -d
docker compose exec app uv run alembic upgrade head

# 헬스체크
curl http://localhost:8000/api/health
# 예상 응답: {"status": "ok"}

# SPA 라우팅 확인
curl -L http://localhost:8000/
# → index.html 반환 (Svelte 앱)

# 정리
docker compose down -v
```

## 검증 절차

1. `docker compose build` 성공 (빌드 오류 없음)
2. `docker compose up -d` 후:
   - `docker compose ps` → app, db 모두 `Up` 상태
   - `curl http://localhost:8000/api/health` → `{"status": "ok"}`
   - `curl http://localhost:8000/` → HTML 반환 (index.html)
   - `curl http://localhost:8000/api/auth/login` (POST 없이) → 405 또는 422 (API 라우터 정상 동작)
3. 체크리스트:
   - `docker compose down -v && docker compose up -d` 재시작 후 DB 데이터가 유지되는가? (postgres_data 볼륨)
   - 업로드 파일이 `uploads_data` 볼륨에 유지되는가?
   - `.env` 파일이 이미지에 포함되지 않는가? (`.dockerignore` 확인)
   - `SECRET_KEY`가 이미지에 하드코딩되지 않는가?
4. `phases/7-docker/index.json` step 0 업데이트:
   - 성공 → `"status": "completed"`, `"summary": "Docker 배포 완성: Multi-stage Dockerfile(Node빌드+Python앱)/docker-compose(app+db)/StaticFiles SPA fallback/볼륨(postgres_data+uploads_data)/healthcheck"`

## 금지사항

- `SECRET_KEY`를 Dockerfile 또는 docker-compose.yml에 하드코딩 금지. 이유: 시크릿 노출
- `POSTGRES_PASSWORD`를 기본값 `changeme`로 프로덕션에서 사용 금지 안내. 이유: `.env`에서 반드시 재설정
- `/app/uploads` 를 StaticFiles로 마운트 금지. 이유: 인증 없이 파일 직접 접근 가능해짐
- API 라우터 등록 전에 StaticFiles 마운트 금지. 이유: SPA fallback이 API 요청을 가로챔
- `pip install` 금지. 이유: uv를 사용하는 프로젝트
