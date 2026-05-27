# Stage 1: Node build (Svelte + Vite)
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
# 결과: /app/frontend/dist/

# Stage 2: Python app
FROM python:3.13-slim AS app
WORKDIR /app

# curl 설치 (HEALTHCHECK용) + libmagic (python-magic용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

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

# 엔트리포인트 스크립트 복사 (마이그레이션 자동 실행)
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

HEALTHCHECK CMD curl -f http://localhost:8000/api/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
