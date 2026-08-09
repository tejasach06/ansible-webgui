import pytest

@pytest.mark.asyncio(loop_scope="session")
async def test_login_flow(client):
    # Missing CSRF header
    res = await client.post("/api/auth/login", json={"username": "admin", "password": "adminpassword123"})
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "csrf_missing"

    # Valid login with CSRF
    res = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "adminpassword123"},
        headers={"X-Requested-With": "XMLHttpRequest"}
    )
    assert res.status_code == 200
    assert "access_token" in res.cookies
    assert "refresh_token" in res.cookies

    # Invalid password
    res = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrongpassword"},
        headers={"X-Requested-With": "XMLHttpRequest"}
    )
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "invalid_credentials"
