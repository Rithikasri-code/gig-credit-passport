"""
Central scoring service — the single place that computes, persists,
hash-chains, and logs a score change, regardless of what triggered it
(a manual "Compute score" click, a fresh data sync, or a self-declared
ITR status change). Having one function for this means auto-rescoring
can't drift out of sync with manual scoring — they're literally the same
code path.
"""
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import Score, SelfReportedEarning, User, ScoreChangeEvent
from app.services.accounts_service import get_user_transactions
from app.scoring.features import compute_features
from app.scoring.model import compute_score
from app.scoring.hash_chain import compute_record_hash


async def gather_current_features(db: AsyncSession, user_id: str) -> dict:
    """The real, current feature vector for a user, from their actual data."""
    txns = await get_user_transactions(db, user_id)
    txn_dicts = [
        {
            "txn_date": t.txn_date.isoformat(),
            "amount": float(t.amount),
            "txn_type": t.txn_type,
            "category": t.category,
            "source_platform": t.source_platform,
        }
        for t in txns
    ]

    result = await db.execute(select(SelfReportedEarning).where(SelfReportedEarning.user_id == user_id))
    self_reported_rows = result.scalars().all()
    self_reported_dicts = [
        {"source_platform": r.source_platform, "total_earnings": float(r.total_earnings) if r.total_earnings else None}
        for r in self_reported_rows
    ]

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    itr_filed = bool(user.itr_filed) if user else False

    return compute_features(txn_dicts, self_reported_dicts, itr_filed=itr_filed)


async def recompute_and_persist_score(db: AsyncSession, user_id: str, trigger: str) -> dict:
    """
    trigger: "manual" | "auto_sync" | "itr_status_change" — recorded on the
    change event so the worker (and any future notification) can see WHY
    their score moved, not just that it did.

    Returns the same shape whether or not a score could actually be
    computed (e.g. no data yet) — callers check result["score_value"].
    """
    features = await gather_current_features(db, user_id)
    result_data = compute_score(features)

    score_row = None
    if result_data["score_value"] is not None:
        # Get the previous score (for both hash-chaining and the change event).
        prev_result = await db.execute(
            select(Score).where(Score.user_id == user_id).order_by(Score.computed_at.desc()).limit(1)
        )
        prev_score_row = prev_result.scalar_one_or_none()
        prev_hash = prev_score_row.record_hash if prev_score_row else ""
        prev_score_value = prev_score_row.score_value if prev_score_row else None

        computed_at = datetime.now(timezone.utc)
        record_hash = compute_record_hash(
            prev_hash, user_id, result_data["score_value"], features, computed_at.isoformat()
        )

        score_row = Score(
            user_id=user_id,
            model_version=result_data["model_version"],
            score_value=result_data["score_value"],
            features_used=features,
            reason_codes=result_data["reason_codes"],
            computed_at=computed_at,
            prev_hash=prev_hash,
            record_hash=record_hash,
        )
        db.add(score_row)

        # Only log a change event if the score is actually new or different —
        # avoids spamming a worker with "your score changed to the same
        # number" noise on every sync.
        if prev_score_value is None or prev_score_value != result_data["score_value"]:
            delta = (result_data["score_value"] - prev_score_value) if prev_score_value is not None else None
            db.add(ScoreChangeEvent(
                user_id=user_id,
                previous_score=prev_score_value,
                new_score=result_data["score_value"],
                delta=delta,
                trigger=trigger,
            ))

        await db.commit()
        await db.refresh(score_row)

    return {
        "score_id": score_row.id if score_row else None,
        "score": result_data["score_value"],
        "reason_codes": result_data["reason_codes"],
        "features": features,
        "model_version": result_data["model_version"],
    }
