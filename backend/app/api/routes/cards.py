from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.card_service import get_card, search_cards, get_all_sets
from app.services.price_service import get_price
from app.schemas.card import CardOut, PriceOut, CardSearchResponse, SetsResponse

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("/search", response_model=CardSearchResponse)
async def search(
    q: str = Query(..., min_length=2),
    set_id: str | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results = await search_cards(q, set_id, limit, db)
    return CardSearchResponse(results=results, total=len(results))


@router.get("/{card_id}/price", response_model=PriceOut)
async def card_price(
    card_id: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    price = await get_price(card_id, db)
    if not price:
        # Return empty price object rather than 404 — price data may just be unavailable
        return PriceOut(card_id=card_id)
    return PriceOut(**price)


@router.get("/{card_id}", response_model=CardOut)
async def card_detail(
    card_id: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = await get_card(card_id, db)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    return CardOut(**card)
