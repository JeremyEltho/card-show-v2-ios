from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.analytics_service import get_summary, get_history
from app.schemas.analytics import AnalyticsSummary, AnalyticsHistory

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
async def analytics_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await get_summary(user.id, db)
    return AnalyticsSummary(**data)


@router.get("/history", response_model=AnalyticsHistory)
async def analytics_history(
    from_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    to_date: date = Query(default_factory=date.today),
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await get_history(user.id, from_date, to_date, granularity, db)
    return AnalyticsHistory(**data)
