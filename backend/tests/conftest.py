from collections.abc import Callable, Iterator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.application import create_app
from app.config import Settings
from app.mock_db import MockDatabase

TEST_SECRET = "test-secret-key-that-is-long-enough-for-hs256"


@dataclass
class Account:
    id: str
    username: str
    email: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


@pytest.fixture
def settings() -> Settings:
    return Settings(
        jwt_secret=TEST_SECRET,
        password_hash_iterations=1_000,  # keep tests fast
        seed_demo_data=False,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings=settings, db=MockDatabase())
    with TestClient(app) as c:
        yield c


@pytest.fixture
def register(client: TestClient) -> Callable[[str], Account]:
    def _register(username: str) -> Account:
        res = client.post(
            "/auth/register",
            json={"email": f"{username}@example.com", "username": username, "password": "password123"},
        )
        assert res.status_code == 201, res.text
        body = res.json()
        return Account(id=body["user"]["id"], username=username, email=body["user"]["email"], token=body["token"])

    return _register


@pytest.fixture
def alice(register: Callable[[str], Account]) -> Account:
    return register("alice")


@pytest.fixture
def bob(register: Callable[[str], Account]) -> Account:
    return register("bob")


@pytest.fixture
def carol(register: Callable[[str], Account]) -> Account:
    return register("carol")


@pytest.fixture
def make_group(client: TestClient) -> Callable[..., dict]:
    """Creates a group owned by `owner` and adds `members` to it. Returns the group JSON."""

    def _make_group(owner: Account, *members: Account, name: str = "Trip") -> dict:
        res = client.post("/groups", json={"name": name}, headers=owner.headers)
        assert res.status_code == 201, res.text
        group = res.json()
        for member in members:
            res = client.post(f"/groups/{group['id']}/members", json={"identifier": member.username}, headers=owner.headers)
            assert res.status_code == 200, res.text
            group = res.json()
        return group

    return _make_group
