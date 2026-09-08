"""
Consent service: the layer between routes and the AA client.
Every consent request, activation, and revocation is persisted here —
this table IS the audit log a worker sees when they ask "who has my data".
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import ConsentArtifact, ConsentStatus
from app.services.aa_client import get_aa_client


async def initiate_consent(db: AsyncSession, user_id: str, purpose: str, data_life_days: int = 90) -> ConsentArtifact:
    aa_client = get_aa_client()
    result = await aa_client.create_consent(user_id=user_id, purpose=purpose)

    consent = ConsentArtifact(
        user_id=user_id,
        aa_consent_handle=result["consent_handle"],
        purpose=purpose,
        fi_types=["DEPOSIT"],
        status=ConsentStatus.ACTIVE if result["status"] == "ACTIVE" else ConsentStatus.PENDING,
        data_life_days=data_life_days,
        expires_at=datetime.now(timezone.utc) + timedelta(days=data_life_days),
    )
    db.add(consent)
    await db.commit()
    await db.refresh(consent)
    return consent


async def refresh_consent_status(db: AsyncSession, consent: ConsentArtifact) -> ConsentArtifact:
    aa_client = get_aa_client()
    live_status = await aa_client.check_consent_status(consent.aa_consent_handle)
    consent.status = ConsentStatus(live_status) if live_status in ConsentStatus.__members__ else consent.status
    await db.commit()
    await db.refresh(consent)
    return consent


async def revoke_consent(db: AsyncSession, consent: ConsentArtifact) -> ConsentArtifact:
    """
    Worker-initiated revocation. This must always be honored immediately —
    it's the core trust promise of the product ('one-tap revoke').
    """
    consent.status = ConsentStatus.REVOKED
    consent.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(consent)
    return consent


async def get_user_consents(db: AsyncSession, user_id: str) -> list[ConsentArtifact]:
    result = await db.execute(
        select(ConsentArtifact).where(ConsentArtifact.user_id == user_id).order_by(ConsentArtifact.requested_at.desc())
    )
    return list(result.scalars().all())
