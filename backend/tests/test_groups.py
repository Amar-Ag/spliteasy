import pytest


def test_create_group_makes_creator_a_member(client, alice):
    res = client.post("/groups", json={"name": "  Ski weekend  "}, headers=alice.headers)

    assert res.status_code == 201
    group = res.json()
    assert group["name"] == "Ski weekend"
    assert group["createdById"] == alice.id
    assert group["members"] == [{"id": alice.id, "email": "alice@example.com", "username": "alice"}]
    assert group["id"] and group["createdAt"]


@pytest.mark.parametrize("name", ["", "   ", "x" * 61])
def test_create_group_validates_name(client, alice, name):
    res = client.post("/groups", json={"name": name}, headers=alice.headers)

    assert res.status_code == 422


def test_list_groups_only_shows_my_groups(client, alice, bob, make_group):
    mine = make_group(alice, name="Mine")
    shared = make_group(bob, alice, name="Shared")
    make_group(bob, name="Bob only")

    res = client.get("/groups", headers=alice.headers)

    assert res.status_code == 200
    groups = res.json()
    assert {g["id"] for g in groups} == {mine["id"], shared["id"]}
    shared_summary = next(g for g in groups if g["id"] == shared["id"])
    assert shared_summary == {"id": shared["id"], "name": "Shared", "memberCount": 2, "myBalanceCents": 0}


def test_list_groups_newest_first(client, alice, make_group):
    first = make_group(alice, name="First")
    second = make_group(alice, name="Second")

    ids = [g["id"] for g in client.get("/groups", headers=alice.headers).json()]

    assert ids == [second["id"], first["id"]]


def test_get_group(client, alice, bob, make_group):
    group = make_group(alice, bob)

    res = client.get(f"/groups/{group['id']}", headers=bob.headers)

    assert res.status_code == 200
    assert [m["username"] for m in res.json()["members"]] == ["alice", "bob"]


def test_get_group_hidden_from_non_members(client, alice, bob, make_group):
    group = make_group(alice)

    assert client.get(f"/groups/{group['id']}", headers=bob.headers).status_code == 404
    assert client.get("/groups/does-not-exist", headers=alice.headers).status_code == 404


@pytest.mark.parametrize("identifier", ["bob", "BOB", "bob@example.com", " Bob@Example.com "])
def test_add_member_by_username_or_email(client, alice, bob, make_group, identifier):
    group = make_group(alice)

    res = client.post(f"/groups/{group['id']}/members", json={"identifier": identifier}, headers=alice.headers)

    assert res.status_code == 200
    assert [m["id"] for m in res.json()["members"]] == [alice.id, bob.id]


def test_added_member_can_see_group(client, alice, bob, make_group):
    group = make_group(alice, bob)

    ids = [g["id"] for g in client.get("/groups", headers=bob.headers).json()]

    assert group["id"] in ids


def test_add_unknown_member_returns_404(client, alice, make_group):
    group = make_group(alice)

    res = client.post(f"/groups/{group['id']}/members", json={"identifier": "ghost"}, headers=alice.headers)

    assert res.status_code == 404


def test_add_existing_member_returns_409(client, alice, bob, make_group):
    group = make_group(alice, bob)

    res = client.post(f"/groups/{group['id']}/members", json={"identifier": "bob"}, headers=alice.headers)

    assert res.status_code == 409


def test_non_member_cannot_add_members(client, alice, bob, carol, make_group):
    group = make_group(alice)

    res = client.post(f"/groups/{group['id']}/members", json={"identifier": "carol"}, headers=bob.headers)

    assert res.status_code == 404


@pytest.mark.parametrize(
    "method, path",
    [
        ("get", "/groups"),
        ("post", "/groups"),
        ("get", "/groups/x"),
        ("post", "/groups/x/members"),
        ("get", "/groups/x/expenses"),
        ("post", "/groups/x/expenses"),
        ("get", "/groups/x/balances"),
        ("get", "/groups/x/settlements"),
        ("post", "/groups/x/settlements"),
    ],
)
def test_group_endpoints_require_auth(client, method, path):
    res = getattr(client, method)(path, **({"json": {}} if method == "post" else {}))

    assert res.status_code == 401
