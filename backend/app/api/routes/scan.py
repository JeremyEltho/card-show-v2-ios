from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import time

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.scan_history import ScanHistory
from app.services.scan_service import identify_card
from app.schemas.scan import ScanRequest, ScanResponse, ScanFailResponse

router = APIRouter(prefix="/scan", tags=["scan"])


@router.post("/identify", response_model=ScanResponse)
async def identify(
    body: ScanRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.ocr_text and not body.image_b64:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either ocr_text or image_b64 is required",
        )

    start_ms = int(time.time() * 1000)
    result = await identify_card(body.ocr_text, body.ocr_confidence, body.image_b64, user.id, db)
    duration_ms = int(time.time() * 1000) - start_ms

    # Log to scan_history
    db.add(ScanHistory(
        user_id=user.id,
        card_id=result["card_id"] if result else None,
        raw_ocr_text=body.ocr_text,
        confidence_score=result["confidence"] if result else None,
        pipeline_stage=result["pipeline"] if result else "failed",
        scan_duration_ms=duration_ms,
        scanned_at=datetime.now(timezone.utc),
    ))
    await db.commit()

    if not result or result["confidence"] < 0.3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not identify card",
        )

    return ScanResponse(**result)
