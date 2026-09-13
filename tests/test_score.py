"""
Score tests — covers the hash-chain tamper detection and the ITR fairness
bug that was caught and fixed earlier, so it can never silently regress.
"""
import pytest
from sqlalchemy import select, update

from tests.conftest import register_and_login, link_and_sync_account
from app.db import session as db_session
from app.models.models import Score


@pytest.mark.asyncio
async def test_compute_score_returns_a_real_score(client):
    session = await register_and_login(client, "9333300001")
    headers = {"Authorization": f"Bearer {session['token']}"}
    await link_and_sync_account(client, session["token"])

    resp = await client.post("/api/v1/score/compute", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] is not None
    assert 300 <= data["score"] <= 900
    assert len(data["reason_codes"]) > 0


@pytest.mark.asyncio
async def test_score_without_any_data_is_not_computed(client):
    session = await register_and_login(client, "9333300002")
    headers = {"Authorization": f"Bearer {session['token']}"}

    resp = await client.post("/api/v1/score/compute", headers=headers)
    assert resp.json()["score"] is None


@pytest.mark.asyncio
async def test_no_self_reported_data_does_not_penalize_the_score(client):
    """
    Regression test for a real bug caught earlier: a worker who never
    uploads an earnings screenshot should not be scored as if their
    (nonexistent) self-reported data were unreliable.
    """
    session = await register_and_login(client, "9333300003")
    headers = {"Authorization": f"Bearer {session['token']}"}
    await link_and_sync_account(client, session["token"])

    resp = await client.post("/api/v1/score/compute", headers=headers)
    reason_codes = resp.json()["reason_codes"]
    assert not any("self-reported" in r.lower() and "reliab" in r.lower() for r in reason_codes)


@pytest.mark.asyncio
async def test_hash_chain_verifies_clean_history(client):
    session = await register_and_login(client, "9333300004")
    headers = {"Authorization": f"Bearer {session['token']}"}
    # link_and_sync_account already triggers one auto-computed score (the
    # auto-rescoring feature) — the two explicit calls below add two more.
    await link_and_sync_account(client, session["token"])

    await client.post("/api/v1/score/compute", headers=headers)
    await client.post("/api/v1/score/compute", headers=headers)

    resp = await client.get("/api/v1/score/verify-integrity", headers=headers)
    data = resp.json()
    assert data["valid"] is True
    assert data["checked"] == 3


@pytest.mark.asyncio
async def test_hash_chain_detects_direct_database_tampering(client):
    """
    The actual security guarantee of the hash chain: even a direct
    database edit (bypassing the API entirely) must be detected.
    """
    session = await register_and_login(client, "9333300005")
    headers = {"Authorization": f"Bearer {session['token']}"}
    # This alone already produces one auto-computed score row — no need
    # for an extra explicit /score/compute call.
    await link_and_sync_account(client, session["token"])

    async with db_session.AsyncSessionLocal() as db:
        result = await db.execute(
            select(Score).where(Score.user_id == session["user_id"]).order_by(Score.computed_at.desc())
        )
        score_row = result.scalars().first()
        await db.execute(
            update(Score).where(Score.id == score_row.id).values(score_value=900)
        )
        await db.commit()

    resp = await client.get("/api/v1/score/verify-integrity", headers=headers)
    data = resp.json()
    assert data["valid"] is False
    assert data["broken_at_score_id"] == score_row.id


@pytest.mark.asyncio
async def test_simulate_does_not_persist_anything(client):
    session = await register_and_login(client, "9333300006")
    headers = {"Authorization": f"Bearer {session['token']}"}
    await link_and_sync_account(client, session["token"])
    await client.post("/api/v1/score/compute", headers=headers)

    before = await client.get("/api/v1/score/history", headers=headers)
    before_count = len(before.json())

    sim_resp = await client.post(
        "/api/v1/score/simulate", json={"itr_filed": True}, headers=headers
    )
    assert sim_resp.status_code == 200
    assert sim_resp.json()["simulated_score"] is not None

    after = await client.get("/api/v1/score/history", headers=headers)
    assert len(after.json()) == before_count  # simulation must not create a real score row
