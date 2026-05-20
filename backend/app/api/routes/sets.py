from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.card_service import get_all_sets
from app.schemas.card import SetsResponse

router = APIRouter(prefix="/sets", tags=["sets"])


@router.get("", response_model=SetsResponse)
async def list_sets(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sets = await get_all_sets(db)
    return SetsResponse(sets=sets, total=len(sets))
