import pytest


@pytest.fixture
def trio(alice, bob, carol, make_group):
    return make_group(alice, bob, carol)


def add_expense(client, group, payer, amount, splits, split_type="amount"):
    res = client.post(
        f"/api/groups/{group['id']}/expenses",
        json={
            "description": "Expense",
            "amountCents": amount,
            "paidById": payer.id,
            "splitType": split_type,
            "splits": [{"userId": a.id, "value": v} for a, v in splits],
        },
        headers=payer.headers,
    )
    assert res.status_code == 201, res.text


def settle(client, group, actor, from_account, to_account, amount):
    return client.post(
        f"/api/groups/{group['id']}/settlements",
        json={"fromUserId": from_account.id, "toUserId": to_account.id, "amountCents": amount},
        headers=actor.headers,
    )


def get_balances(client, group, account):
    res = client.get(f"/api/groups/{group['id']}/balances", headers=account.headers)
    assert res.status_code == 200, res.text
    return res.json()


def test_new_group_is_settled(client, alice, bob, carol, trio):
    balances = get_balances(client, trio, alice)

    assert balances == {
        "net": [
            {"userId": alice.id, "amountCents": 0},
            {"userId": bob.id, "amountCents": 0},
            {"userId": carol.id, "amountCents": 0},
        ],
        "transfers": [],
    }


def test_expense_creates_debts_to_payer(client, alice, bob, carol, trio):
    add_expense(client, trio, alice, 3000, [(alice, 1000), (bob, 1000), (carol, 1000)])

    balances = get_balances(client, trio, bob)

    assert {n["userId"]: n["amountCents"] for n in balances["net"]} == {alice.id: 2000, bob.id: -1000, carol.id: -1000}
    assert balances["transfers"] == [
        {"fromUserId": bob.id, "toUserId": alice.id, "amountCents": 1000},
        {"fromUserId": carol.id, "toUserId": alice.id, "amountCents": 1000},
    ]


def test_debts_are_simplified(client, alice, bob, carol, trio):
    # bob owes alice 10, carol owes bob 10  ->  carol pays alice 10 directly
    add_expense(client, trio, alice, 1000, [(bob, 1000)])
    add_expense(client, trio, bob, 1000, [(carol, 1000)])

    balances = get_balances(client, trio, alice)

    assert balances["transfers"] == [{"fromUserId": carol.id, "toUserId": alice.id, "amountCents": 1000}]


def test_net_balances_always_sum_to_zero(client, alice, bob, carol, trio):
    add_expense(client, trio, alice, 1000, [(alice, 33.34), (bob, 33.33), (carol, 33.33)], split_type="percent")
    add_expense(client, trio, bob, 777, [(alice, 400), (carol, 377)])

    balances = get_balances(client, trio, alice)

    assert sum(n["amountCents"] for n in balances["net"]) == 0


def test_record_settlement(client, alice, bob, carol, trio):
    add_expense(client, trio, alice, 3000, [(alice, 1000), (bob, 1000), (carol, 1000)])

    res = settle(client, trio, bob, bob, alice, 400)

    assert res.status_code == 201
    body = res.json()
    assert body["groupId"] == trio["id"]
    assert (body["fromUserId"], body["toUserId"], body["amountCents"]) == (bob.id, alice.id, 400)
    assert body["createdById"] == bob.id
    assert body["id"] and body["createdAt"]

    transfers = get_balances(client, trio, alice)["transfers"]
    assert {"fromUserId": bob.id, "toUserId": alice.id, "amountCents": 600} in transfers


def test_full_settlement_clears_balances(client, alice, bob, trio):
    add_expense(client, trio, alice, 2000, [(bob, 2000)])

    settle(client, trio, alice, bob, alice, 2000)  # any member may record a payment

    balances = get_balances(client, trio, alice)
    assert balances["transfers"] == []
    assert all(n["amountCents"] == 0 for n in balances["net"])


def test_group_list_reflects_my_balance(client, alice, bob, trio):
    add_expense(client, trio, alice, 2000, [(bob, 2000)])

    alice_view = client.get("/api/groups", headers=alice.headers).json()
    bob_view = client.get("/api/groups", headers=bob.headers).json()

    assert alice_view[0]["myBalanceCents"] == 2000
    assert bob_view[0]["myBalanceCents"] == -2000


def test_list_settlements_newest_first(client, alice, bob, trio):
    first = settle(client, trio, alice, bob, alice, 100).json()
    second = settle(client, trio, alice, bob, alice, 200).json()

    res = client.get(f"/api/groups/{trio['id']}/settlements", headers=alice.headers)

    assert res.status_code == 200
    assert [s["id"] for s in res.json()] == [second["id"], first["id"]]


def test_settlement_validation(client, alice, bob, register, trio):
    outsider = register("outsider")

    same_person = settle(client, trio, alice, alice, alice, 100)
    non_member = settle(client, trio, alice, outsider, alice, 100)
    zero = settle(client, trio, alice, bob, alice, 0)
    negative = settle(client, trio, alice, bob, alice, -5)

    assert same_person.status_code == 422 and "different" in same_person.json()["detail"]
    assert non_member.status_code == 422 and "member" in non_member.json()["detail"]
    assert zero.status_code == 422
    assert negative.status_code == 422


def test_non_members_cannot_access_balances_or_settlements(client, alice, bob, register, trio):
    outsider = register("outsider")

    assert client.get(f"/api/groups/{trio['id']}/balances", headers=outsider.headers).status_code == 404
    assert client.get(f"/api/groups/{trio['id']}/settlements", headers=outsider.headers).status_code == 404
    assert settle(client, trio, outsider, bob, alice, 100).status_code == 404
