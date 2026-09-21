import pytest
from fastapi.testclient import TestClient

from app.application import create_app
from app.config import Settings
from app.sql_database import SqlDatabase
from tests.conftest import TEST_SECRET, sqlite_file_url


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_cors_preflight_allows_frontend_origin(client, origin):
    res = client.options(
        "/api/groups",
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
    res = client.get("/api/groups", headers={**alice.headers, "Origin": "http://localhost:5173"})

    assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_unknown_origin(client):
    res = client.options(
        "/api/groups",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert "access-control-allow-origin" not in res.headers


def app_settings(database_url: str, seed: bool = False) -> Settings:
    return Settings(jwt_secret=TEST_SECRET, password_hash_iterations=1_000, seed_demo_data=seed, database_url=database_url)


def login(client: TestClient, identifier: str, password: str = "password123") -> dict[str, str]:
    res = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


def test_demo_data_is_seeded_when_enabled():
    with TestClient(create_app(settings=app_settings("sqlite://", seed=True))) as client:
        groups = {g["name"]: g for g in client.get("/api/groups", headers=login(client, "alice")).json()}

    assert groups["Lisbon Trip"]["myBalanceCents"] == 14775
    assert groups["Apartment 4B"]["myBalanceCents"] == -3000


def test_app_creates_schema_and_persists_data_across_restarts(tmp_path):
    settings = app_settings(sqlite_file_url(tmp_path))

    with TestClient(create_app(settings=settings)) as client:
        client.post("/api/auth/register", json={"email": "zoe@example.com", "username": "zoe", "password": "password123"})
        headers = login(client, "zoe")
        client.post("/api/groups", json={"name": "Book club"}, headers=headers)

    with TestClient(create_app(settings=settings)) as client:  # fresh app, same database file
        groups = client.get("/api/groups", headers=login(client, "zoe")).json()

    assert [g["name"] for g in groups] == ["Book club"]


def test_tokens_survive_restart_when_secret_is_fixed(tmp_path):
    settings = app_settings(sqlite_file_url(tmp_path))

    with TestClient(create_app(settings=settings)) as client:
        client.post("/api/auth/register", json={"email": "zoe@example.com", "username": "zoe", "password": "password123"})
        headers = login(client, "zoe")
        client.post("/api/auth/logout", headers=login(client, "zoe"))  # revoke a different session

    with TestClient(create_app(settings=settings)) as client:
        assert client.get("/api/auth/me", headers=headers).status_code == 200


def test_logout_revocation_survives_restart(tmp_path):
    settings = app_settings(sqlite_file_url(tmp_path))

    with TestClient(create_app(settings=settings)) as client:
        client.post("/api/auth/register", json={"email": "zoe@example.com", "username": "zoe", "password": "password123"})
        headers = login(client, "zoe")
        client.post("/api/auth/logout", headers=headers)

    with TestClient(create_app(settings=settings)) as client:
        assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_demo_data_is_only_seeded_once(tmp_path):
    settings = app_settings(sqlite_file_url(tmp_path), seed=True)

    with TestClient(create_app(settings=settings)):
        pass
    with TestClient(create_app(settings=settings)) as client:
        groups = client.get("/api/groups", headers=login(client, "alice")).json()

    assert sorted(g["name"] for g in groups) == ["Apartment 4B", "Lisbon Trip"]


def test_register_race_on_unique_constraint_returns_409(settings):
    """If two sign-ups pass the existence check at the same time, the database constraint still wins."""

    class RacyDatabase(SqlDatabase):
        def get_user_by_email(self, email):  # pretend the other request hasn't committed yet
            return None

        def get_user_by_username(self, username):
            return None

    db = RacyDatabase.from_url("sqlite://")
    db.create_schema()
    try:
        with TestClient(create_app(settings=settings, db=db)) as client:
            body = {"email": "zoe@example.com", "username": "zoe", "password": "password123"}
            assert client.post("/api/auth/register", json=body).status_code == 201
            second = client.post("/api/auth/register", json=body)
    finally:
        db.close()

    assert second.status_code == 409
    assert "already exists" in second.json()["detail"]


# ---- Serving the built frontend ----


@pytest.fixture
def static_dir(tmp_path):
    root = tmp_path / "static"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>SplitEasy</title>")
    (root / "assets" / "index-abc123.js").write_text("console.log('app')")
    (root / "favicon.svg").write_text("<svg/>")
    (tmp_path / "secret.txt").write_text("not part of the site")
    return root


@pytest.fixture
def ui_client(settings, static_dir):
    app = create_app(settings=Settings(**{**vars(settings), "static_dir": str(static_dir)}))
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("path", ["/", "/login", "/groups/abc123", "/anything/deep"])
def test_frontend_routes_serve_index_html(ui_client, path):
    """A refresh on any client-side route must return the app, not a 404."""
    res = ui_client.get(path)

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert "SplitEasy" in res.text


def test_static_files_are_served(ui_client):
    js = ui_client.get("/assets/index-abc123.js")
    icon = ui_client.get("/favicon.svg")

    assert js.status_code == 200 and "console.log" in js.text
    assert icon.status_code == 200 and "svg" in icon.text


def test_api_still_wins_over_the_frontend(ui_client):
    """/api/groups is the API even though /groups/... is a page in the UI."""
    unauthorised = ui_client.get("/api/groups")
    login_res = ui_client.post("/api/auth/register", json={"email": "z@example.com", "username": "zoe", "password": "password123"})

    assert unauthorised.status_code == 401
    assert unauthorised.json()["detail"]
    assert login_res.status_code == 201
    assert ui_client.get("/health").json() == {"status": "ok"}


def test_unknown_api_path_does_not_fall_back_to_the_app(ui_client):
    res = ui_client.get("/api/nope")

    assert res.status_code == 404
    assert "text/html" not in res.headers["content-type"]


def test_paths_outside_the_static_directory_are_not_served(ui_client):
    res = ui_client.get("/../secret.txt")

    assert res.status_code in (200, 404)
    assert "not part of the site" not in res.text


def test_frontend_is_not_served_without_static_dir(client):
    assert client.get("/login").status_code == 404
