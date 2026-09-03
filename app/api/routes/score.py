from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.models import Score, ScoreChangeEvent
from app.services.scoring_service import gather_current_features, recompute_and_persist_score
from app.scoring.model import compute_score
from app.scoring.hash_chain import verify_chain
from app.api.deps import get_current_user_id

router = APIRouter()


@router.post("/compute")
async def compute_user_score(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Recomputes the score fresh from current data. This is intentionally
    stateless-in-computation but persists the result + explanation, so
    every score a worker has ever gotten stays auditable — and hash-
    chained to every prior score, so the history can't be silently edited.
    """
    return await recompute_and_persist_score(db, current_user_id, trigger="manual")


class SimulateRequest(BaseModel):
    """
    Hypothetical adjustments to try against the worker's CURRENT real
    feature baseline. Every field is optional — only send what you want
    to change. None of this touches real data or persists anything.
    """
    itr_filed: bool | None = None  # simulate filing (or un-filing) taxes
    additional_months_of_history: int = 0  # simulate N more months of steady history
    additional_platforms: int = 0  # simulate onboarding N more gig platforms
    additional_self_reported_confirmation: float = 0.0  # simulate uploading more confirmed earnings (0-1 boost)


@router.post("/simulate")
async def simulate_score(
    req: SimulateRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    "What if" planning tool — projects the score under a hypothetical
    change without persisting anything or touching real data. This is
    what turns the passport from a rearview mirror into something a
    worker can actually plan around.
    """
    baseline_features = await gather_current_features(db, current_user_id)

    if baseline_features.get("months_of_history", 0) == 0:
        raise HTTPException(400, "Link and sync an account first — nothing to simulate from yet.")

    baseline_result = compute_score(baseline_features)

    simulated_features = dict(baseline_features)
    if req.itr_filed is not None:
        simulated_features["itr_filed"] = 1.0 if req.itr_filed else 0.0
    if req.additional_months_of_history:
        simulated_features["months_of_history"] = baseline_features["months_of_history"] + req.additional_months_of_history
    if req.additional_platforms:
        simulated_features["num_active_platforms"] = baseline_features["num_active_platforms"] + req.additional_platforms
    if req.additional_self_reported_confirmation:
        simulated_features["self_reported_confirmation_ratio"] = min(
            1.0,
            baseline_features["self_reported_confirmation_ratio"] + req.additional_self_reported_confirmation,
        )
        simulated_features["_has_self_reported_data"] = True

    simulated_result = compute_score(simulated_features)

    delta = None
    if baseline_result["score_value"] is not None and simulated_result["score_value"] is not None:
        delta = simulated_result["score_value"] - baseline_result["score_value"]

    return {
        "current_score": baseline_result["score_value"],
        "simulated_score": simulated_result["score_value"],
        "delta": delta,
        "simulated_reason_codes": simulated_result["reason_codes"],
    }


@router.get("/events")
async def list_score_events(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Every time this worker's score changed, and why (manual click, a data
    sync, or an ITR status change) — the feed a notification UI would read
    from. Marks returned events as seen.
    """
    result = await db.execute(
        select(ScoreChangeEvent)
        .where(ScoreChangeEvent.user_id == current_user_id)
        .order_by(ScoreChangeEvent.created_at.desc())
    )
    events = result.scalars().all()

    unseen = [e for e in events if not e.seen]
    for e in unseen:
        e.seen = True
    if unseen:
        await db.commit()

    return [
        {
            "id": e.id,
            "previous_score": e.previous_score,
            "new_score": e.new_score,
            "delta": e.delta,
            "trigger": e.trigger,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


@router.get("/history")
async def score_history(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    """Every score ever computed for this worker — the passport's track record."""
    result = await db.execute(
        select(Score).where(Score.user_id == current_user_id).order_by(Score.computed_at.desc())
    )
    scores = result.scalars().all()
    return [
        {
            "id": s.id,
            "score": s.score_value,
            "reason_codes": s.reason_codes,
            "model_version": s.model_version,
            "computed_at": s.computed_at.isoformat(),
        }
        for s in scores
    ]


@router.get("/verify-integrity")
async def verify_score_integrity(
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Recomputes the entire hash chain for this worker's score history and
    confirms nothing has been altered. Exposed so a worker (or an auditor
    on their behalf) can independently verify their own history hasn't
    been tampered with — not just trust that it hasn't.
    """
    result = await db.execute(
        select(Score).where(Score.user_id == current_user_id).order_by(Score.computed_at.asc())
    )
    scores = result.scalars().all()

    if not scores:
        return {"valid": True, "checked": 0, "message": "No score history yet."}

    scores_dicts = [
        {
            "id": s.id,
            "prev_hash": s.prev_hash,
            "record_hash": s.record_hash,
            "user_id": s.user_id,
            "score_value": s.score_value,
            "features_used": s.features_used,
            "computed_at": s.computed_at.isoformat(),
        }
        for s in scores
    ]

    is_valid, broken_id = verify_chain(scores_dicts)
    return {
        "valid": is_valid,
        "checked": len(scores),
        "broken_at_score_id": broken_id,
    }
