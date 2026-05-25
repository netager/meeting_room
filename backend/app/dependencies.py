from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Employee

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Employee:
    # Phase 1에서 구현
    raise NotImplementedError


async def require_admin(user: Employee = Depends(get_current_user)) -> Employee:
    # Phase 1에서 구현
    raise NotImplementedError


async def require_room_manager(user: Employee = Depends(get_current_user)) -> Employee:
    # Phase 1에서 구현
    raise NotImplementedError


async def require_active_user(user: Employee = Depends(get_current_user)) -> Employee:
    # Phase 1에서 구현
    raise NotImplementedError
