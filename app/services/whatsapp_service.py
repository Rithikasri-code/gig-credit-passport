"""
WhatsApp-style command interface.

Design notes:
- Identity is the phone number itself — same as real WhatsApp, where the
  platform (Meta/Twilio) has already verified the sender owns that number
  before the message ever reaches us. No OTP needed here; the phone
  number IS the credential, same trust model as an actual WhatsApp
  Business integration. A user must have already signed up via the app
  once (so we have a User row for that phone number) — this bridges
  in, it doesn't replace, the OTP-based account creation.
- Every reply is short, plain-language, and works in a chat bubble — no
  tables, no JSON, nothing that assumes a screen wider than a phone.
- The actual message-delivery layer (sending a real WhatsApp message back)
  is mocked here the same way the OTP SMS gateway is mocked — this
  function returns the reply text; whatever calls it is responsible for
  actually sending it, which today is just the webhook echoing it back
  in DEBUG mode, and would be a real WhatsApp Business API / Twilio call
  in production.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import User, Score
from app.services.scoring_service import gather_current_features, recompute_and_persist_score
from app.scoring.model import compute_score
from app.services import passport_service

HELP_TEXT = (
    "Here's what I can do:\n"
    "- \"score\": your current passport score\n"
    "- \"simulate itr\": see how filing taxes would change your score\n"
    "- \"passport\": get a shareable passport link\n"
    "- \"help\": show this again"
)

NOT_REGISTERED_TEXT = (
    "I don't recognize this number yet. Please sign up in the Gig Credit Passport app first, "
    "then message me again."
)


async def _get_user_by_phone(db: AsyncSession, phone_number: str) -> User | None:
    result = await db.execute(select(User).where(User.phone_number == phone_number))
    return result.scalar_one_or_none()


async def _handle_score(db: AsyncSession, user: User) -> str:
    result = await db.execute(
        select(Score).where(Score.user_id == user.id).order_by(Score.computed_at.desc()).limit(1)
    )
    latest = result.scalar_one_or_none()
    if not latest:
        return "You don't have a score yet. Link a bank account in the app first, then message me again."

    reasons = "\n".join(f"- {r}" for r in latest.reason_codes[:3])
    return f"Your Passport Score is {latest.score_value} of 900.\n\nTop reasons:\n{reasons}"


async def _handle_simulate_itr(db: AsyncSession, user: User) -> str:
    features = await gather_current_features(db, user.id)
    if features.get("months_of_history", 0) == 0:
        return "Link a bank account in the app first, then message me again."

    current = compute_score(features)
    simulated_features = dict(features)
    simulated_features["itr_filed"] = 1.0
    simulated = compute_score(simulated_features)

    if current["score_value"] is None or simulated["score_value"] is None:
        return "Couldn't run that simulation right now. Try again shortly."

    delta = simulated["score_value"] - current["score_value"]
    if user.itr_filed:
        return f"You've already filed your ITR. It's already counted in your score of {current['score_value']}."
    if delta > 0:
        return f"Filing your ITR could raise your score by about {delta} points, to ~{simulated['score_value']}."
    return f"Filing your ITR wouldn't change your score much right now (about {delta:+d} points)."


async def _handle_passport(db: AsyncSession, user: User) -> str:
    result = await db.execute(
        select(Score).where(Score.user_id == user.id).order_by(Score.computed_at.desc()).limit(1)
    )
    latest = result.scalar_one_or_none()
    if not latest:
        return "You don't have a score yet. Link a bank account in the app first, then message me again."

    passport = await passport_service.issue_passport(db, user.id, latest.id)
    return (
        f"Here's your shareable passport: passport ID {passport.id}\n"
        f"Score: {passport.score_value_snapshot} of 900. Valid until "
        f"{passport.expires_at.strftime('%d %b %Y')}.\n"
        "Anyone can verify this is real without needing your login."
    )


async def handle_message(db: AsyncSession, phone_number: str, message: str) -> str:
    """Main entry point — takes an incoming message, returns the reply text."""
    user = await _get_user_by_phone(db, phone_number)
    if not user:
        return NOT_REGISTERED_TEXT

    text = message.strip().lower()

    if text in ("hi", "hello", "start", "menu"):
        return f"Hi {user.full_name}! " + HELP_TEXT
    if text == "help":
        return HELP_TEXT
    if text == "score":
        return await _handle_score(db, user)
    if text in ("simulate itr", "simulate", "itr"):
        return await _handle_simulate_itr(db, user)
    if text == "passport":
        return await _handle_passport(db, user)

    return "Sorry, I didn't understand that.\n\n" + HELP_TEXT
