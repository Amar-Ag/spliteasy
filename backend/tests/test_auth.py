from datetime import datetime, timedelta, timezone

import jwt
import pytest

from tests.conftest import TEST_SECRET


def test_register_returns_token_and_public_user(client):
    res = client.post("/auth/register", json={"email": "Zoe@Example.com", "username": "zoe", "password": "password123"})

    assert res.status_code == 201
    body = res.json()
    assert isinstance(body["token"], str) and body["token"]
    assert body["user"]["username"] == "zoe"
    assert body["user"]["email"] == "zoe@example.com"  # normalised
    assert set(body["user"]) == {"id", "email", "username"}  # never leaks the password hash


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"email": "not-an-email", "username": "zoe", "password": "password123"}, "valid email"),
        ({"email": "zoe@example.com", "username": "z", "password": "password123"}, "Username"),
        ({"email": "zoe@example.com", "username": "bad name!", "password": "password123"}, "Username"),
        ({"email": "zoe@example.com", "username": "zoe", "password": "short"}, "at least 8"),
    ],
)
def test_register_validates_input(client, payload, message):
    res = client.post("/auth/register", json=payload)

    assert res.status_code == 422
    assert message in res.json()["detail"]


def test_register_missing_field_returns_readable_422(client):
    res = client.post("/auth/register", json={"email": "zoe@example.com"})

    assert res.status_code == 422
    assert isinstance(res.json()["detail"], str)


def test_register_rejects_duplicate_email(client, alice):
    res = client.post("/auth/register", json={"email": "ALICE@example.com", "username": "alice2", "password": "password123"})

    assert res.status_code == 409


def test_register_rejects_duplicate_username_case_insensitively(client, alice):
    res = client.post("/auth/register", json={"email": "other@example.com", "username": "Alice", "password": "password123"})

    assert res.status_code == 409


@pytest.mark.parametrize("identifier", ["alice", "ALICE", "alice@example.com", "Alice@Example.com"])
def test_login_with_username_or_email(client, alice, identifier):
    res = client.post("/auth/login", json={"identifier": identifier, "password": "password123"})

    assert res.status_code == 200
    assert res.json()["user"]["id"] == alice.id
    assert res.json()["token"]


@pytest.mark.parametrize("identifier, password", [("alice", "wrong-password"), ("nobody", "password123")])
def test_login_rejects_bad_credentials(client, alice, identifier, password):
    res = client.post("/auth/login", json={"identifier": identifier, "password": password})

    assert res.status_code == 401


def test_me_returns_current_user(client, alice):
    res = client.get("/auth/me", headers=alice.headers)

    assert res.status_code == 200
    assert res.json() == {"id": alice.id, "email": "alice@example.com", "username": "alice"}


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer not-a-jwt"}, {"Authorization": "Basic abc"}],
)
def test_me_requires_valid_token(client, headers):
    res = client.get("/auth/me", headers=headers)

    assert res.status_code == 401


def test_expired_token_is_rejected(client, alice):
    claims = jwt.decode(alice.token, TEST_SECRET, algorithms=["HS256"])
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    expired = jwt.encode({**claims, "exp": past}, TEST_SECRET, algorithm="HS256")

    res = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})

    assert res.status_code == 401


def test_token_signed_with_other_secret_is_rejected(client, alice):
    claims = jwt.decode(alice.token, TEST_SECRET, algorithms=["HS256"])
    forged = jwt.encode(claims, "some-other-secret-that-is-also-long-enough", algorithm="HS256")

    res = client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})

    assert res.status_code == 401


def test_logout_revokes_token(client, alice):
    res = client.post("/auth/logout", headers=alice.headers)
    assert res.status_code == 204

    assert client.get("/auth/me", headers=alice.headers).status_code == 401


def test_logout_only_revokes_that_session(client, alice):
    second = client.post("/auth/login", json={"identifier": "alice", "password": "password123"}).json()["token"]

    client.post("/auth/logout", headers=alice.headers)

    assert client.get("/auth/me", headers={"Authorization": f"Bearer {second}"}).status_code == 200
