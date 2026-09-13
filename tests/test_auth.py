"""
Auth tests — converts the manual curl verification from earlier sessions
into real, repeatable assertions.
"""
import pytest

from tests.conftest import register_and_login


@pytest.mark.asyncio
async def test_otp_request_returns_debug_otp_in_debug_mode(client):
    resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": "9111100001"})
    assert resp.status_code == 200
    assert "debug_otp" in resp.json()
    assert len(resp.json()["debug_otp"]) == 6


@pytest.mark.asyncio
async def test_wrong_otp_is_rejected(client):
    await client.post("/api/v1/auth/otp/request", json={"phone_number": "9111100002"})
    resp = await client.post(
        "/api/v1/auth/otp/verify",
        json={"phone_number": "9111100002", "otp": "000000", "full_name": "X"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_correct_otp_issues_a_working_token(client):
    session = await register_and_login(client, "9111100003")
    assert session["token"]
    assert session["user_id"]

    # The token should actually work against a protected endpoint.
    resp = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {session['token']}"}
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == session["user_id"]


@pytest.mark.asyncio
async def test_protected_endpoint_rejects_missing_token(client):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_rejects_garbage_token(client):
    resp = await client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer this-is-not-a-real-token"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_otp_cooldown_blocks_rapid_second_request(client):
    phone = "9111100004"
    first = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone})
    assert first.status_code == 200

    second = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone})
    assert second.status_code == 429


@pytest.mark.asyncio
async def test_otp_rate_limit_is_scoped_per_phone_number(client):
    """A rate-limited number shouldn't affect a different, fresh number."""
    phone_a = "9111100005"
    phone_b = "9111100006"

    await client.post("/api/v1/auth/otp/request", json={"phone_number": phone_a})
    blocked = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone_a})
    assert blocked.status_code == 429

    fresh = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone_b})
    assert fresh.status_code == 200
