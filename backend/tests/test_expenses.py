import pytest


@pytest.fixture
def trio(alice, bob, carol, make_group):
    return make_group(alice, bob, carol)


def post_expense(client, account, group, **overrides):
    payload = {
        "description": "Dinner",
        "amountCents": 3000,
        "paidById": account.id,
        "splitType": "amount",
        "splits": [],
        **overrides,
    }
    return client.post(f"/groups/{group['id']}/expenses", json=payload, headers=account.headers)


def test_create_expense_split_by_amount(client, alice, bob, carol, trio):
    res = post_expense(
        client, alice, trio,
        splits=[{"userId": alice.id, "value": 1000}, {"userId": bob.id, "value": 1500}, {"userId": carol.id, "value": 500}],
    )

    assert res.status_code == 201
    expense = res.json()
    assert expense["groupId"] == trio["id"]
    assert expense["description"] == "Dinner"
    assert expense["amountCents"] == 3000
    assert expense["paidById"] == alice.id
    assert expense["createdById"] == alice.id
    assert expense["splitType"] == "amount"
    assert expense["splits"] == [
        {"userId": alice.id, "amountCents": 1000, "percent": None},
        {"userId": bob.id, "amountCents": 1500, "percent": None},
        {"userId": carol.id, "amountCents": 500, "percent": None},
    ]


def test_create_expense_split_by_percent_allocates_every_cent(client, alice, bob, carol, trio):
    res = post_expense(
        client, bob, trio,
        amountCents=8450,
        paidById=bob.id,
        splitType="percent",
        splits=[{"userId": alice.id, "value": 50}, {"userId": bob.id, "value": 25}, {"userId": carol.id, "value": 25}],
    )

    assert res.status_code == 201
    splits = res.json()["splits"]
    assert [s["amountCents"] for s in splits] == [4225, 2113, 2112]
    assert [s["percent"] for s in splits] == [50, 25, 25]


def test_percent_split_accepts_two_decimal_places(client, alice, bob, carol, trio):
    res = post_expense(
        client, alice, trio,
        amountCents=1000,
        splitType="percent",
        splits=[{"userId": alice.id, "value": 33.34}, {"userId": bob.id, "value": 33.33}, {"userId": carol.id, "value": 33.33}],
    )

    assert res.status_code == 201
    assert sum(s["amountCents"] for s in res.json()["splits"]) == 1000


def test_zero_value_splits_are_dropped(client, alice, bob, carol, trio):
    res = post_expense(
        client, alice, trio,
        splits=[{"userId": alice.id, "value": 3000}, {"userId": bob.id, "value": 0}],
    )

    assert res.status_code == 201
    assert [s["userId"] for s in res.json()["splits"]] == [alice.id]


def test_description_is_trimmed(client, alice, trio):
    res = post_expense(client, alice, trio, description="  Taxi  ", splits=[{"userId": alice.id, "value": 3000}])

    assert res.json()["description"] == "Taxi"


@pytest.mark.parametrize(
    "overrides_fn, message",
    [
        (lambda a, b, o: {"description": "   ", "splits": [{"userId": a.id, "value": 3000}]}, "Description"),
        (lambda a, b, o: {"amountCents": 0, "splits": [{"userId": a.id, "value": 0}]}, "greater than zero"),
        (lambda a, b, o: {"amountCents": -100, "splits": [{"userId": a.id, "value": -100}]}, "greater than zero"),
        (lambda a, b, o: {"splits": [{"userId": a.id, "value": 1000}]}, "add up"),
        (lambda a, b, o: {"splits": [{"userId": a.id, "value": 1500.5}, {"userId": b.id, "value": 1499.5}]}, "whole cents"),
        (lambda a, b, o: {"splitType": "percent", "splits": [{"userId": a.id, "value": 60}, {"userId": b.id, "value": 30}]}, "100%"),
        (lambda a, b, o: {"splitType": "percent", "splits": [{"userId": a.id, "value": 50.005}, {"userId": b.id, "value": 49.995}]}, "decimal"),
        (lambda a, b, o: {"paidById": o.id, "splits": [{"userId": a.id, "value": 3000}]}, "payer"),
        (lambda a, b, o: {"splits": [{"userId": o.id, "value": 3000}]}, "member"),
        (lambda a, b, o: {"splits": [{"userId": a.id, "value": 1500}, {"userId": a.id, "value": 1500}]}, "once"),
        (lambda a, b, o: {"splits": [{"userId": a.id, "value": 3500}, {"userId": b.id, "value": -500}]}, "negative"),
        (lambda a, b, o: {"splits": []}, "at least one"),
        (lambda a, b, o: {"splits": [{"userId": a.id, "value": 0}]}, "at least one"),
    ],
)
def test_create_expense_validation(client, alice, bob, register, trio, overrides_fn, message):
    outsider = register("outsider")

    res = post_expense(client, alice, trio, **overrides_fn(alice, bob, outsider))

    assert res.status_code == 422, res.text
    assert message.lower() in res.json()["detail"].lower()


def test_invalid_split_type_is_rejected(client, alice, trio):
    res = post_expense(client, alice, trio, splitType="shares", splits=[{"userId": alice.id, "value": 3000}])

    assert res.status_code == 422


def test_list_expenses_newest_first(client, alice, trio):
    first = post_expense(client, alice, trio, description="First", splits=[{"userId": alice.id, "value": 3000}]).json()
    second = post_expense(client, alice, trio, description="Second", splits=[{"userId": alice.id, "value": 3000}]).json()

    res = client.get(f"/groups/{trio['id']}/expenses", headers=alice.headers)

    assert res.status_code == 200
    assert [e["id"] for e in res.json()] == [second["id"], first["id"]]


def test_expenses_are_scoped_to_their_group(client, alice, trio, make_group):
    other = make_group(alice, name="Other")
    post_expense(client, alice, other, splits=[{"userId": alice.id, "value": 3000}])

    assert client.get(f"/groups/{trio['id']}/expenses", headers=alice.headers).json() == []


def test_non_members_cannot_see_or_add_expenses(client, alice, register, trio):
    outsider = register("outsider")

    assert client.get(f"/groups/{trio['id']}/expenses", headers=outsider.headers).status_code == 404
    res = post_expense(client, outsider, trio, splits=[{"userId": alice.id, "value": 3000}])
    assert res.status_code == 404
