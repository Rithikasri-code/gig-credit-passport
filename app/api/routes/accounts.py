from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.models import ConsentArtifact
from app.services import accounts_service
from app.services.scoring_service import recompute_and_persist_score
from app.api.deps import get_current_user_id, require_self

router = APIRouter()


@router.post("/sync/{consent_id}")
async def sync(
    consent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Pull financial data through an ACTIVE consent and persist it, then
    automatically recompute the score — a worker shouldn't have to
    remember to click "compute" every time fresh data lands. If scoring
    fails for any reason, the sync itself still succeeds; a stale score
    is recoverable, a lost sync isn't.
    """
    result = await db.execute(select(ConsentArtifact).where(ConsentArtifact.id == consent_id))
    consent = result.scalar_one_or_none()
    if not consent:
        raise HTTPException(404, "Consent not found")
    require_self(consent.user_id, current_user_id)

    try:
        accounts = await accounts_service.sync_financial_data(db, consent)
    except ValueError as e:
        raise HTTPException(400, str(e))

    score_result = None
    try:
        score_result = await recompute_and_persist_score(db, current_user_id, trigger="auto_sync")
    except Exception:
        pass  # sync succeeded; scoring can be retried manually if this ever fails

    return {
        "accounts_synced": len(accounts),
        "accounts": [
            {"id": a.id, "fip_id": a.fip_id, "masked_account_number": a.masked_account_number}
            for a in accounts
        ],
        "score": score_result["score"] if score_result else None,
    }


@router.get("/mine/transactions")
async def list_my_transactions(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    txns = await accounts_service.get_user_transactions(db, current_user_id)
    return [
        {
            "id": t.id,
            "date": t.txn_date.isoformat(),
            "amount": float(t.amount),
            "type": t.txn_type,
            "narration": t.narration,
            "category": t.category,
            "source_platform": t.source_platform,
        }
        for t in txns
    ]

