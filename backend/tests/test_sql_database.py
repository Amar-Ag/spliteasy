"""Contract tests for the SQLAlchemy implementation of the `Database` protocol."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.database import DuplicateError
from app.models import Expense, ExpenseSplit, Group, Settlement, User, new_id
from app.sql_database import SqlDatabase
from tests.conftest import sqlite_file_url

T0 = datetime(2026, 1, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)


def make_user(username: str, **overrides) -> User:
    fields = dict(id=new_id(), email=f"{username}@example.com", username=username, password_hash="hash", created_at=T0)
    return User(**{**fields, **overrides})


def make_group(creator: User, *members: User, created_at: datetime = T0, name: str = "Group") -> Group:
    return Group(
        id=new_id(), name=name, created_by_id=creator.id, created_at=created_at,
        member_ids=[creator.id, *(m.id for m in members)],
    )


def make_expense(group: Group, payer: User, splits: list[ExpenseSplit], created_at: datetime = T0, **overrides) -> Expense:
    fields = dict(
        id=new_id(), group_id=group.id, description="Dinner", amount_cents=sum(s.amount_cents for s in splits),
        paid_by_id=payer.id, split_type="amount", splits=splits, created_by_id=payer.id, created_at=created_at,
    )
    return Expense(**{**fields, **overrides})


def make_settlement(group: Group, payer: User, payee: User, cents: int, created_at: datetime = T0) -> Settlement:
    return Settlement(
        id=new_id(), group_id=group.id, from_user_id=payer.id, to_user_id=payee.id, amount_cents=cents,
        created_by_id=payer.id, created_at=created_at,
    )


@pytest.fixture
def alice(db: SqlDatabase) -> User:
    user = make_user("alice")
    db.add_user(user)
    return user


@pytest.fixture
def bob(db: SqlDatabase) -> User:
    user = make_user("bob")
    db.add_user(user)
    return user


# ---- Users ----


def test_user_round_trip_keeps_utc_timestamp(db, alice):
    loaded = db.get_user(alice.id)

    assert loaded == alice
    assert loaded.created_at.tzinfo is not None
    assert loaded.created_at == T0


def test_missing_records_return_none(db):
    assert db.get_user("nope") is None
    assert db.get_user_by_email("nope@example.com") is None
    assert db.get_user_by_username("nope") is None
    assert db.get_group("nope") is None


def test_user_lookups_are_case_insensitive(db, alice):
    assert db.get_user_by_email("ALICE@Example.com").id == alice.id
    assert db.get_user_by_username("AlIcE").id == alice.id


def test_non_utc_timestamps_are_normalised(db):
    plus_two = timezone(timedelta(hours=2))
    user = make_user("zoe", created_at=datetime(2026, 1, 1, 14, 0, tzinfo=plus_two))
    db.add_user(user)

    assert db.get_user(user.id).created_at == datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "duplicate",
    [
        lambda: make_user("alice2", email="alice@example.com"),
        lambda: make_user("ALICE", email="other@example.com"),
    ],
    ids=["same-email", "same-username-different-case"],
)
def test_duplicate_users_raise(db, alice, duplicate):
    with pytest.raises(DuplicateError):
        db.add_user(duplicate())

    assert db.get_user_by_username("alice").id == alice.id  # original untouched


# ---- Groups ----


def test_group_round_trip_keeps_member_order(db, alice, bob):
    group = make_group(bob, alice)
    db.add_group(group)

    assert db.get_group(group.id) == group
    assert db.get_group(group.id).member_ids == [bob.id, alice.id]


def test_add_group_member_appends_and_is_idempotent(db, alice, bob):
    group = make_group(alice)
    db.add_group(group)

    db.add_group_member(group.id, bob.id)
    db.add_group_member(group.id, bob.id)

    assert db.get_group(group.id).member_ids == [alice.id, bob.id]


def test_list_groups_for_user_only_returns_memberships_newest_first(db, alice, bob):
    older = make_group(alice, created_at=T0, name="older")
    newer = make_group(alice, bob, created_at=T0 + timedelta(days=1), name="newer")
    bobs = make_group(bob, created_at=T0 + timedelta(days=2), name="bob only")
    for g in (newer, bobs, older):  # insertion order differs from creation order
        db.add_group(g)

    assert [g.name for g in db.list_groups_for_user(alice.id)] == ["newer", "older"]
    assert [g.name for g in db.list_groups_for_user(bob.id)] == ["bob only", "newer"]


def test_same_timestamp_falls_back_to_insertion_order(db, alice):
    first = make_group(alice, name="first")
    second = make_group(alice, name="second")
    db.add_group(first)
    db.add_group(second)

    assert [g.name for g in db.list_groups_for_user(alice.id)] == ["second", "first"]


def test_returned_records_are_detached_copies(db, alice, bob):
    group = make_group(alice)
    db.add_group(group)

    loaded = db.get_group(group.id)
    loaded.member_ids.append(bob.id)
    loaded.name = "changed"

    assert db.get_group(group.id) == group


# ---- Expenses ----


def test_expense_round_trip_with_splits(db, alice, bob):
    group = make_group(alice, bob)
    db.add_group(group)
    expense = make_expense(
        group, alice,
        splits=[ExpenseSplit(bob.id, 4225, 50.0), ExpenseSplit(alice.id, 4225, 50.0)],
        split_type="percent",
    )
    db.add_expense(expense)

    [loaded] = db.list_expenses(group.id)
    assert loaded == expense
    assert [s.user_id for s in loaded.splits] == [bob.id, alice.id]


def test_amount_split_percent_is_none(db, alice):
    group = make_group(alice)
    db.add_group(group)
    db.add_expense(make_expense(group, alice, splits=[ExpenseSplit(alice.id, 100)]))

    assert db.list_expenses(group.id)[0].splits[0].percent is None


def test_expenses_and_settlements_newest_first_and_scoped_to_group(db, alice, bob):
    group, other = make_group(alice, bob), make_group(alice)
    db.add_group(group)
    db.add_group(other)
    later = make_expense(group, alice, [ExpenseSplit(bob.id, 100)], created_at=T0 + timedelta(hours=1), description="later")
    earlier = make_expense(group, alice, [ExpenseSplit(bob.id, 100)], created_at=T0, description="earlier")
    db.add_expense(later)
    db.add_expense(earlier)
    db.add_expense(make_expense(other, alice, [ExpenseSplit(alice.id, 100)], description="elsewhere"))
    db.add_settlement(make_settlement(group, bob, alice, 50, created_at=T0))
    db.add_settlement(make_settlement(group, bob, alice, 70, created_at=T0 + timedelta(hours=2)))

    assert [e.description for e in db.list_expenses(group.id)] == ["later", "earlier"]
    assert [s.amount_cents for s in db.list_settlements(group.id)] == [70, 50]
    assert db.list_settlements(other.id) == []


def test_foreign_keys_are_enforced(db, alice):
    orphan = make_expense(make_group(alice), alice, [ExpenseSplit(alice.id, 100)])  # group never saved

    with pytest.raises(IntegrityError):
        db.add_expense(orphan)


# ---- Revoked tokens ----


def test_revoked_tokens(db):
    future = datetime.now(timezone.utc) + timedelta(hours=1)

    assert not db.is_token_revoked("jti-1")
    db.revoke_token("jti-1", future)
    db.revoke_token("jti-1", future)  # idempotent

    assert db.is_token_revoked("jti-1")
    assert not db.is_token_revoked("jti-2")


def test_revoking_purges_expired_tokens(db):
    db.revoke_token("old", datetime.now(timezone.utc) - timedelta(seconds=1))
    db.revoke_token("new", datetime.now(timezone.utc) + timedelta(hours=1))

    assert not db.is_token_revoked("old")
    assert db.is_token_revoked("new")


# ---- Persistence ----


def test_data_survives_reopening_the_database_file(tmp_path):
    url = sqlite_file_url(tmp_path)
    first = SqlDatabase.from_url(url)
    first.create_schema()
    user = make_user("alice")
    first.add_user(user)
    group = make_group(user)
    first.add_group(group)
    first.close()

    second = SqlDatabase.from_url(url)
    second.create_schema()  # safe to run against an existing schema
    try:
        assert second.get_user(user.id) == user
        assert second.get_group(group.id) == group
    finally:
        second.close()
