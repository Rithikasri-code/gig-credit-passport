"""
Consent tests — the core trust promise ("one-tap revoke actually blocks
access") converted from manual curl testing into a real assertion.
"""
import pytest

from tests.conftest import register_and_login


@pytest.mark.asyncio
async def test_consent_initiate_activates_via_mock_aa(client):
    session = await register_and_login(client, "9222200001")
    headers = {"Authorization": f"Bearer {session['token']}"}

    resp = await client.post("/api/v1/consent/initiate", json={"purpose": "test"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_sync_via_active_consent_populates_transactions(client):
    session = await register_and_login(client, "9222200002")
    headers = {"Authorization": f"Bearer {session['token']}"}

    consent_resp = await client.post("/api/v1/consent/initiate", json={"purpose": "test"}, headers=headers)
    consent_id = consent_resp.json()["id"]

    sync_resp = await client.post(f"/api/v1/accounts/sync/{consent_id}", headers=headers)
    assert sync_resp.status_code == 200
    assert sync_resp.json()["accounts_synced"] == 1

    txns_resp = await client.get("/api/v1/accounts/mine/transactions", headers=headers)
    assert len(txns_resp.json()) > 0


@pytest.mark.asyncio
async def test_revoking_consent_actually_blocks_further_sync(client):
    """
    This is the core trust promise of the whole product: revoke must
    genuinely stop data access, not just flip a cosmetic status flag.
    """
    session = await register_and_login(client, "9222200003")
    headers = {"Authorization": f"Bearer {session['token']}"}

    consent_resp = await client.post("/api/v1/consent/initiate", json={"purpose": "test"}, headers=headers)
    consent_id = consent_resp.json()["id"]

    revoke_resp = await client.post(f"/api/v1/consent/{consent_id}/revoke", headers=headers)
    assert revoke_resp.json()["status"] == "REVOKED"

    blocked_sync = await client.post(f"/api/v1/accounts/sync/{consent_id}", headers=headers)
    assert blocked_sync.status_code == 400


@pytest.mark.asyncio
async def test_user_cannot_revoke_another_users_consent(client):
    """Cross-user isolation — one worker cannot touch another's consent."""
    session_a = await register_and_login(client, "9222200004")
    session_b = await register_and_login(client, "9222200005")

    headers_a = {"Authorization": f"Bearer {session_a['token']}"}
    headers_b = {"Authorization": f"Bearer {session_b['token']}"}

    consent_resp = await client.post("/api/v1/consent/initiate", json={"purpose": "test"}, headers=headers_a)
    consent_id = consent_resp.json()["id"]

    forbidden = await client.post(f"/api/v1/consent/{consent_id}/revoke", headers=headers_b)
    assert forbidden.status_code == 403
