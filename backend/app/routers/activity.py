from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user
from ..config import settings
from ..db import get_db
from ..models import User
from ..services import analytics
from ..services.ratelimit import limiter

router = APIRouter(prefix="/api/me", tags=["activity"])


@router.post("/heartbeat", status_code=204)
@limiter.limit(settings.rate_limit_heartbeat)
async def heartbeat(request: Request, response: Response,
                    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """The app was visible and in use for (up to) the last interval. No body: nothing about what
    was on screen is sent or stored."""
    await analytics.record_heartbeat(db, user.id)
    return Response(status_code=204)
