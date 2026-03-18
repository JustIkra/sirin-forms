from fastapi import APIRouter, Request
from sqlalchemy import text

from app.utils.dt import now

router = APIRouter()


@router.get("/health")
async def health_check(request: Request) -> dict:
    status = {"status": "ok", "timestamp": now().isoformat()}

    # Check database
    try:
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception as exc:
        status["database"] = f"error: {exc}"
        status["status"] = "degraded"

    return status
