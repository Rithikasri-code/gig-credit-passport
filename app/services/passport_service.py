"""
Verifiable, shareable passport credentials.

A worker can issue a passport from any of their scores and hand the
resulting link/ID to a lender, landlord, or platform. Verification is
public (no login) so a third party can check validity without ever
touching the worker's account or raw data — this is what makes "you own
your data" a technical reality rather than a UI claim.

Signing uses HMAC-SHA256 over the passport's content with the app's
SECRET_KEY. This proves the passport was genuinely issued by this backend
and hasn't been altered (e.g. someone editing the score_value in a shared
link) — it does NOT make the passport independently verifiable without
hitting our API, since that needs asymmetric signing (RSA/EdDSA) instead
of HMAC. That upgrade is straightforward later (swap HMAC for a signing
keypair) without changing the credential's shape — noted here rather than
silently pretending this is already fully self-sovereign.
"""
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.models import Passport, Score, gen_uuid, PassportVerificationLog

PASSPORT_VALIDITY_DAYS = 30


def _score_band(score_value: int) -> str:
    if score_value >= 750:
        return "Good"
    if score_value >= 600:
        return "Fair"
    return "Needs work"


def _sign(passport_id: str, user_id: str, score_id: str, score_value: int, issued_at: str, expires_at: str) -> str:
    payload = f"{passport_id}|{user_id}|{score_id}|{score_value}|{issued_at}|{expires_at}"
    return hmac.new(settings.PASSPORT_SIGNING_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


async def issue_passport(db: AsyncSession, user_id: str, score_id: str) -> Passport:
    result = await db.execute(select(Score).where(Score.id == score_id, Score.user_id == user_id))
    score = result.scalar_one_or_none()
    if not score:
        raise ValueError("Score not found or does not belong to this user.")

    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(days=PASSPORT_VALIDITY_DAYS)

    # Generate the id upfront (rather than via a flush round-trip) so the
    # signature can be computed before the row is ever inserted — avoids
    # a transient NOT NULL violation on the signature column.
    passport_id = gen_uuid()
    signature = _sign(
        passport_id, user_id, score.id, score.score_value, issued_at.isoformat(), expires_at.isoformat()
    )

    passport = Passport(
        id=passport_id,
        user_id=user_id,
        score_id=score.id,
        score_value_snapshot=score.score_value,
        issued_at=issued_at,
        expires_at=expires_at,
        signature=signature,
    )
    db.add(passport)
    await db.commit()
    await db.refresh(passport)
    return passport


async def revoke_passport(db: AsyncSession, passport: Passport) -> Passport:
    passport.revoked = True
    passport.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(passport)
    return passport


async def verify_passport(db: AsyncSession, passport_id: str, requester_ip: str | None = None) -> dict:
    """
    Public verification — no auth required. Returns only what a third
    party needs (validity, score band, expiry) — never the full feature
    breakdown or raw transaction data, which stays behind login.

    Every check is logged (passport_id, requester IP, outcome), since this
    is the one endpoint in the whole system that's deliberately reachable
    by anyone with no login — logging is what makes it possible to notice
    abuse (e.g. one IP enumerating passport IDs) that nothing else here
    would catch.
    """
    result = await verify_passport_no_log(db, passport_id)

    db.add(PassportVerificationLog(
        passport_id=passport_id,
        requester_ip=requester_ip,
        was_valid=result["valid"],
        reason=result.get("reason"),
    ))
    await db.commit()

    return result


async def verify_passport_no_log(db: AsyncSession, passport_id: str) -> dict:
    """The actual verification logic, separated so it can be tested/reused without side effects."""
    result = await db.execute(select(Passport).where(Passport.id == passport_id))
    passport = result.scalar_one_or_none()

    if not passport:
        return {"valid": False, "reason": "Passport not found."}

    expected_signature = _sign(
        passport.id,
        passport.user_id,
        passport.score_id,
        passport.score_value_snapshot,
        passport.issued_at.isoformat(),
        passport.expires_at.isoformat(),
    )
    if not hmac.compare_digest(expected_signature, passport.signature):
        return {"valid": False, "reason": "Signature mismatch — this passport may have been tampered with."}

    if passport.revoked:
        return {"valid": False, "reason": "This passport has been revoked by the worker."}

    if passport.expires_at < datetime.now(timezone.utc):
        return {"valid": False, "reason": "This passport has expired."}

    return {
        "valid": True,
        "score_band": _score_band(passport.score_value_snapshot),
        "score_value": passport.score_value_snapshot,
        "issued_at": passport.issued_at.isoformat(),
        "expires_at": passport.expires_at.isoformat(),
    }
