from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services import ocr_service
from app.api.deps import get_current_user_id

router = APIRouter()


@router.post("/upload")
async def upload_earnings_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Upload a gig-platform earnings screenshot. Always self-reported and
    unverified until cross-checked against AA transaction data — the
    response makes this explicit so the frontend never presents it as
    equivalent to verified income.
    """
    contents = await file.read()
    extracted = ocr_service.extract_from_image_bytes(contents)
    record = ocr_service.build_self_reported_earning(current_user_id, extracted)

    db.add(record)
    await db.commit()
    await db.refresh(record)

    return {
        "id": record.id,
        "source_platform": record.source_platform,
        "total_earnings": float(record.total_earnings) if record.total_earnings else None,
        "trip_or_order_count": record.trip_or_order_count,
        "rating": float(record.rating) if record.rating else None,
        "extraction_confidence": record.extraction_confidence,
        "is_verified": record.is_verified,
        "note": "Self-reported from an uploaded document. Not verified against bank data yet.",
    }
