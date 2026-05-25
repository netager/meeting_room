import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.db import AsyncSessionLocal
from app.models import AuditLog

logger = structlog.get_logger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        try:
            await self._record_audit(request, response)
        except Exception:
            pass  # best-effort — 감사 로그 실패가 응답을 막지 않음
        return response

    async def _record_audit(self, request: Request, response) -> None:
        # Phase 6에서 행위자 추출 등 세부 로직 완성
        # 현재는 로그인/로그아웃/데이터 변경 API만 대상으로 하는 기본 구조
        method = request.method
        path = request.url.path

        # 정적 파일, 헬스체크, 토큰 갱신은 제외
        skip_paths = {"/api/health", "/api/auth/token/refresh"}
        if path in skip_paths or not path.startswith("/api/"):
            return
        if method == "GET":
            return

        actor = "anonymous"
        ip_address = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")

        async with AsyncSessionLocal() as session:
            audit = AuditLog(
                actor=actor,
                action="CREATE" if method == "POST" else "UPDATE" if method in ("PUT", "PATCH") else "DELETE",
                target_table=None,
                target_id=None,
                detail=f"{method} {path} → {response.status_code}",
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else None,
            )
            session.add(audit)
            await session.commit()

    def _get_client_ip(self, request: Request) -> str:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        if request.client:
            return request.client.host
        return ""
