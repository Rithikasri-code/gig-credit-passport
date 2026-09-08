"""
Phone-based OTP auth service.

Design choices:
- Phone + OTP, not email/password — matches how gig workers actually
  authenticate everywhere else (UPI apps, gig platforms themselves).
- OTP is never logged or returned in production. In DEBUG mode we return
  it in the API response so local development/testing doesn't need a
  real SMS gateway wired up yet — this must be removed/gated before
  going live (see the DEBUG check below).
- Rate-limit-shaped: attempts are capped per challenge, and old
  unconsumed challenges naturally expire.
"""
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import settings
from app.core.security import hash_otp, verify_otp_hash, create_access_token
from app.models.models import OTPChallenge, User

OTP_LENGTH = 6
OTP_TTL_MINUTES = 5
MAX_VERIFY_ATTEMPTS = 5

# Rate limiting: caps how many OTPs a single phone number can request in a
# rolling window, and enforces a minimum gap between consecutive requests.
# This is table-based (not in-memory) so it holds up across multiple
# server processes/workers, not just a single instance.
MAX_REQUESTS_PER_WINDOW = 5
RATE_LIMIT_WINDOW_MINUTES = 60
MIN_SECONDS_BETWEEN_REQUESTS = 30


class RateLimitExceeded(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _generate_otp() -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(OTP_LENGTH))


async def _check_rate_limit(db: AsyncSession, phone_number: str) -> None:
    now = datetime.now(timezone.utc)

    # 1. Minimum gap since the last request (blocks rapid-fire spamming)
    last_result = await db.execute(
        select(OTPChallenge.created_at)
        .where(OTPChallenge.phone_number == phone_number)
        .order_by(OTPChallenge.created_at.desc())
        .limit(1)
    )
    last_created = last_result.scalar_one_or_none()
    if last_created and (now - last_created).total_seconds() < MIN_SECONDS_BETWEEN_REQUESTS:
        wait = MIN_SECONDS_BETWEEN_REQUESTS - int((now - last_created).total_seconds())
        raise RateLimitExceeded(f"Please wait {wait} seconds before requesting another OTP.")

    # 2. Total requests within the rolling window (blocks sustained abuse)
    window_start = now - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
    count_result = await db.execute(
        select(func.count(OTPChallenge.id))
        .where(OTPChallenge.phone_number == phone_number, OTPChallenge.created_at >= window_start)
    )
    count = count_result.scalar_one()
    if count >= MAX_REQUESTS_PER_WINDOW:
        raise RateLimitExceeded(
            f"Too many OTP requests for this number. Try again in {RATE_LIMIT_WINDOW_MINUTES} minutes."
        )


async def request_otp(db: AsyncSession, phone_number: str) -> dict:
    await _check_rate_limit(db, phone_number)

    otp = _generate_otp()
    challenge = OTPChallenge(
        phone_number=phone_number,
        otp_hash=hash_otp(otp),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES),
    )
    db.add(challenge)
    await db.commit()

    # TODO: wire up a real SMS gateway (e.g. MSG91, Twilio) before production.
    # Until then, OTP is only ever exposed in DEBUG mode for local testing.
    response = {"message": "OTP sent", "expires_in_minutes": OTP_TTL_MINUTES}
    if settings.DEBUG:
        response["debug_otp"] = otp  # NEVER present this field outside DEBUG
    return response


async def verify_otp(db: AsyncSession, phone_number: str, otp: str, full_name: str | None = None) -> dict:
    """
    Verifies OTP, auto-creates the user on first successful verification
    (so signup and login are the same flow — one less step for the worker),
    and returns an access token.
    """
    result = await db.execute(
        select(OTPChallenge)
        .where(OTPChallenge.phone_number == phone_number, OTPChallenge.consumed == False)  # noqa: E712
        .order_by(OTPChallenge.created_at.desc())
    )
    challenge = result.scalars().first()

    if not challenge:
        return {"success": False, "error": "No active OTP request for this number. Request a new one."}

    if challenge.expires_at < datetime.now(timezone.utc):
        return {"success": False, "error": "OTP expired. Request a new one."}

    if challenge.attempts >= MAX_VERIFY_ATTEMPTS:
        return {"success": False, "error": "Too many attempts. Request a new OTP."}

    challenge.attempts += 1

    if not verify_otp_hash(otp, challenge.otp_hash):
        await db.commit()
        return {"success": False, "error": "Incorrect OTP."}

    challenge.consumed = True
    await db.commit()

    # Find or create the user
    user_result = await db.execute(select(User).where(User.phone_number == phone_number))
    user = user_result.scalar_one_or_none()
    if not user:
        user = User(phone_number=phone_number, full_name=full_name or "Gig Worker")
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token(user.id)
    return {"success": True, "access_token": token, "token_type": "bearer", "user_id": user.id}
