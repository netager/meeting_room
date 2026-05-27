#!/bin/sh
# Docker 컨테이너 시작 시 마이그레이션을 자동으로 실행 후 앱 시작
set -e

echo "=== Alembic 마이그레이션 실행 ==="
uv run alembic upgrade head
echo "=== 마이그레이션 완료 ==="

echo "=== 서버 시작 ==="
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
