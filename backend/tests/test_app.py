import pytest
from fastapi.testclient import TestClient

from app.application import create_app
from app.config import Settings
from tests.conftest import TEST_SECRET


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_cors_preflight_allows_frontend_origin(client, origin):
    res = client.options(
        "/groups",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == origin
    allowed_headers = res.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allowed_headers and "content-type" in allowed_headers


def test_cors_headers_on_actual_response(client, alice):
    res = client.get("/groups", headers={**alice.headers, "Origin": "http://localhost:5173"})

    assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_unknown_origin(client):
    res = client.options(
        "/groups",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert "access-control-allow-origin" not in res.headers


def test_demo_data_is_seeded_when_enabled():
    settings = Settings(jwt_secret=TEST_SECRET, password_hash_iterations=1_000, seed_demo_data=True)

    with TestClient(create_app(settings=settings)) as client:
        login = client.post("/auth/login", json={"identifier": "alice", "password": "password123"})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['token']}"}

        groups = {g["name"]: g for g in client.get("/groups", headers=headers).json()}
        assert groups["Lisbon Trip"]["myBalanceCents"] == 14775
        assert groups["Apartment 4B"]["myBalanceCents"] == -3000
