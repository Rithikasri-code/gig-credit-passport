from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.models import ConsentArtifact
from app.services import consent_service
from app.api.deps import get_current_user_id, require_self

router = APIRouter()


class ConsentRequest(BaseModel):
    purpose: str = "Gig Credit Passport: income and repayment scoring"
    data_life_days: int = 90


class ConsentResponse(BaseModel):
    id: str
    status: str
    aa_consent_handle: str
    expires_at: str | None
    model_config = ConfigDict(from_attributes=True)


@router.post("/initiate", response_model=ConsentResponse)
async def initiate(
    req: ConsentRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    consent = await consent_service.initiate_consent(db, current_user_id, req.purpose, req.data_life_days)
    return ConsentResponse(
        id=consent.id,
        status=consent.status.value,
        aa_consent_handle=consent.aa_consent_handle,
        expires_at=consent.expires_at.isoformat() if consent.expires_at else None,
    )


@router.get("/{consent_id}/status")
async def status(
    consent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(select(ConsentArtifact).where(ConsentArtifact.id == consent_id))
    consent = result.scalar_one_or_none()
    if not consent:
        raise HTTPException(404, "Consent not found")
    require_self(consent.user_id, current_user_id)
    consent = await consent_service.refresh_consent_status(db, consent)
    return {"id": consent.id, "status": consent.status.value}


@router.post("/{consent_id}/revoke")
async def revoke(
    consent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(select(ConsentArtifact).where(ConsentArtifact.id == consent_id))
    consent = result.scalar_one_or_none()
    if not consent:
        raise HTTPException(404, "Consent not found")
    require_self(consent.user_id, current_user_id)
    consent = await consent_service.revoke_consent(db, consent)
    return {"id": consent.id, "status": consent.status.value}


@router.get("/mine")
async def list_mine(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    """The audit trail: every consent this worker has ever granted, and its current state."""
    consents = await consent_service.get_user_consents(db, current_user_id)
    return [
        {
            "id": c.id,
            "purpose": c.purpose,
            "status": c.status.value,
            "requested_at": c.requested_at.isoformat(),
            "expires_at": c.expires_at.isoformat() if c.expires_at else None,
            "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
        }
        for c in consents
    ]

