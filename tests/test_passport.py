"""
Passport tests — the shareable, verifiable credential feature. Covers
public verification, revocation, and tamper detection via the HMAC
signature, converting the manual curl testing into real assertions.
"""
import pytest

from tests.conftest import register_and_login, link_and_sync_account
from app.db import session as db_session
from sqlalchemy import update, select as sa_select
from app.models.models import Passport, PassportVerificationLog


async def _issue_passport(client, headers) -> dict:
    history = await client.get("/api/v1/score/history", headers=headers)
    score_id = history.json()[0]["id"]
    resp = await client.post("/api/v1/passport/issue", json={"score_id": score_id}, headers=headers)
    return resp.json()


@pytest.mark.asyncio
async def test_issued_passport_is_publicly_verifiable_with_no_auth(client):
    session = await register_and_login(client, "9444400001")
    headers = {"Authorization": f"Bearer {session['token']}"}
    await link_and_sync_account(client, session["token"])
    await client.post("/api/v1/score/compute", headers=headers)

    passport = await _issue_passport(client, headers)

    # Deliberately no Authorization header — this is the whole point.
    verify_resp = await client.get(f"/api/v1/passport/verify/{passport['id']}")
    assert verify_resp.status_code == 200
    data = verify_resp.json()
    assert data["valid"] is True
    assert data["score_value"] == passport["score_value"]


@pytest.mark.asyncio
async def test_forged_passport_id_is_rejected(client):
    resp = await client.get("/api/v1/passport/verify/00000000-0000-0000-0000-000000000099")
    assert resp.json()["valid"] is False


@pytest.mark.asyncio
async def test_revoked_passport_fails_verification(client):
    session = await register_and_login(client, "9444400002")
    headers = {"Authorization": f"Bearer {session['token']}"}
    await link_and_sync_account(client, session["token"])
    await client.post("/api/v1/score/compute", headers=headers)

    passport = await _issue_passport(client, headers)
    await client.post(f"/api/v1/passport/{passport['id']}/revoke", headers=headers)

    verify_resp = await client.get(f"/api/v1/passport/verify/{passport['id']}")
    data = verify_resp.json()
    assert data["valid"] is False
    assert "revoked" in data["reason"].lower()


@pytest.mark.asyncio
async def test_tampering_with_stored_score_is_caught_by_signature(client):
    """
    The actual security guarantee of the passport: even editing the
    database directly (bypassing the API) must be caught, since the HMAC
    signature won't match the altered content.
    """
    session = await register_and_login(client, "9444400003")
    headers = {"Authorization": f"Bearer {session['token']}"}
    await link_and_sync_account(client, session["token"])
    await client.post("/api/v1/score/compute", headers=headers)

    passport = await _issue_passport(client, headers)

    async with db_session.AsyncSessionLocal() as db:
        await db.execute(
            update(Passport).where(Passport.id == passport["id"]).values(score_value_snapshot=900)
        )
        await db.commit()

    verify_resp = await client.get(f"/api/v1/passport/verify/{passport['id']}")
    data = verify_resp.json()
    assert data["valid"] is False
    assert "signature" in data["reason"].lower()


@pytest.mark.asyncio
async def test_user_cannot_revoke_another_users_passport(client):
    session_a = await register_and_login(client, "9444400004")
    session_b = await register_and_login(client, "9444400005")

    headers_a = {"Authorization": f"Bearer {session_a['token']}"}
    headers_b = {"Authorization": f"Bearer {session_b['token']}"}

    await link_and_sync_account(client, session_a["token"])
    await client.post("/api/v1/score/compute", headers=headers_a)
    passport = await _issue_passport(client, headers_a)

    forbidden = await client.post(f"/api/v1/passport/{passport['id']}/revoke", headers=headers_b)
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_verification_attempts_are_audit_logged(client):
    """
    The public verify endpoint has no auth, so logging is the only way to
    notice abuse — confirm every check (valid or not) actually gets
    recorded, with the correct outcome.
    """
    session = await register_and_login(client, "9444400006")
    headers = {"Authorization": f"Bearer {session['token']}"}
    await link_and_sync_account(client, session["token"])
    await client.post("/api/v1/score/compute", headers=headers)
    passport = await _issue_passport(client, headers)

    await client.get(f"/api/v1/passport/verify/{passport['id']}")
    await client.get("/api/v1/passport/verify/00000000-0000-0000-0000-000000000099")

    async with db_session.AsyncSessionLocal() as db:
        result = await db.execute(sa_select(PassportVerificationLog))
        logs = result.scalars().all()

    assert len(logs) == 2
    outcomes = {log.passport_id: log.was_valid for log in logs}
    assert outcomes[passport["id"]] is True
    assert outcomes["00000000-0000-0000-0000-000000000099"] is False
