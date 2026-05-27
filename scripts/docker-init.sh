#!/bin/bash
# 첫 실행 시 마이그레이션 + 초기 admin 계정 확인
# 사용법: docker compose exec app bash scripts/docker-init.sh
set -e

echo "=== DB 마이그레이션 실행 ==="
uv run alembic upgrade head
echo "마이그레이션 완료"

echo "=== 초기 admin 계정 확인 ==="
uv run python -c "
import asyncio
from app.db import AsyncSessionLocal
from app.repositories import auth_repo

async def main():
    async with AsyncSessionLocal() as db:
        await auth_repo.create_admin_account_if_not_exists(db)
        print('초기 admin 계정 확인 완료 (admin / admin123)')

asyncio.run(main())
"
echo "=== 초기화 완료 ==="
