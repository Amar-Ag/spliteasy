"""Demo data matching the frontend mock, so both behave the same during development."""

from datetime import timedelta

from app.config import Settings
from app.database import Database
from app.models import Expense, ExpenseSplit, Group, Settlement, User, new_id, utcnow
from app.money import allocate_proportional
from app.security import hash_password

DEMO_PASSWORD = "password123"


def seed_demo_data(db: Database, settings: Settings) -> None:
    now = utcnow()

    def days_ago(days: int):
        return now - timedelta(days=days)

    users: dict[str, User] = {}
    for username in ("alice", "bob", "carol", "dave"):
        user = User(
            id=new_id(),
            email=f"{username}@example.com",
            username=username,
            password_hash=hash_password(DEMO_PASSWORD, settings.password_hash_iterations),
            created_at=days_ago(60),
        )
        db.add_user(user)
        users[username] = user

    alice, bob, carol = users["alice"].id, users["bob"].id, users["carol"].id

    def even(total: int, member_ids: list[str]) -> list[ExpenseSplit]:
        amounts = allocate_proportional(total, [1] * len(member_ids))
        return [ExpenseSplit(user_id=uid, amount_cents=a) for uid, a in zip(member_ids, amounts)]

    flat = Group(id=new_id(), name="Apartment 4B", created_by_id=bob, created_at=days_ago(30), member_ids=[alice, bob])
    trip = Group(id=new_id(), name="Lisbon Trip", created_by_id=alice, created_at=days_ago(12), member_ids=[alice, bob, carol])
    db.add_group(flat)
    db.add_group(trip)

    dinner = allocate_proportional(8450, [5000, 2500, 2500])
    expenses = [
        Expense(
            id=new_id(), group_id=flat.id, description="Internet — March", amount_cents=6000, paid_by_id=bob,
            split_type="amount", splits=even(6000, [alice, bob]), created_by_id=bob, created_at=days_ago(5),
        ),
        Expense(
            id=new_id(), group_id=trip.id, description="Airbnb (3 nights)", amount_cents=36000, paid_by_id=alice,
            split_type="amount", splits=even(36000, [alice, bob, carol]), created_by_id=alice, created_at=days_ago(10),
        ),
        Expense(
            id=new_id(), group_id=trip.id, description="Dinner at Time Out Market", amount_cents=8450, paid_by_id=bob,
            split_type="percent",
            splits=[
                ExpenseSplit(user_id=alice, amount_cents=dinner[0], percent=50),
                ExpenseSplit(user_id=bob, amount_cents=dinner[1], percent=25),
                ExpenseSplit(user_id=carol, amount_cents=dinner[2], percent=25),
            ],
            created_by_id=bob, created_at=days_ago(8),
        ),
    ]
    # The mock database lists newest-first by insertion order, so insert oldest first.
    for expense in sorted(expenses, key=lambda e: e.created_at):
        db.add_expense(expense)

    db.add_settlement(
        Settlement(
            id=new_id(), group_id=trip.id, from_user_id=carol, to_user_id=alice, amount_cents=5000,
            created_by_id=carol, created_at=days_ago(6),
        )
    )
