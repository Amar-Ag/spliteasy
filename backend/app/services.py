"""Business rules, independent of HTTP and of the storage implementation."""

import re

from app.config import Settings
from app.database import Database
from app.errors import Conflict, NotFound, Unauthorized, Unprocessable
from app.models import Expense, ExpenseSplit, Group, Settlement, User, new_id, utcnow
from app.money import allocate_proportional, compute_net_balances
from app.schemas import ExpenseCreateIn, RegisterIn, SettlementCreateIn
from app.security import hash_password, verify_password

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
MIN_PASSWORD_LENGTH = 8
MAX_GROUP_NAME_LENGTH = 60
FULL_PERCENT_HUNDREDTHS = 10_000


def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents) / 100:,.2f}"


# ---- Users ----


def find_user(db: Database, identifier: str) -> User | None:
    """Look up a user by email or username (case-insensitive)."""
    needle = identifier.strip()
    return db.get_user_by_email(needle) or db.get_user_by_username(needle)


def register_user(db: Database, settings: Settings, data: RegisterIn) -> User:
    email = data.email.strip().lower()
    username = data.username.strip()

    if not EMAIL_RE.match(email):
        raise Unprocessable("Enter a valid email address")
    if not USERNAME_RE.match(username):
        raise Unprocessable("Username must be 3-20 letters, numbers or underscores")
    if len(data.password) < MIN_PASSWORD_LENGTH:
        raise Unprocessable(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if db.get_user_by_email(email):
        raise Conflict("An account with that email already exists")
    if db.get_user_by_username(username):
        raise Conflict("That username is taken")

    user = User(
        id=new_id(),
        email=email,
        username=username,
        password_hash=hash_password(data.password, settings.password_hash_iterations),
        created_at=utcnow(),
    )
    db.add_user(user)
    return user


def authenticate(db: Database, identifier: str, password: str) -> User:
    user = find_user(db, identifier)
    if user is None or not verify_password(password, user.password_hash):
        raise Unauthorized("Incorrect email/username or password")
    return user


# ---- Groups ----


def create_group(db: Database, creator: User, name: str) -> Group:
    name = name.strip()
    if not name:
        raise Unprocessable("Group name is required")
    if len(name) > MAX_GROUP_NAME_LENGTH:
        raise Unprocessable(f"Group name must be {MAX_GROUP_NAME_LENGTH} characters or fewer")

    group = Group(id=new_id(), name=name, created_by_id=creator.id, created_at=utcnow(), member_ids=[creator.id])
    db.add_group(group)
    return group


def get_member_group(db: Database, group_id: str, user_id: str) -> Group:
    group = db.get_group(group_id)
    # Non-members get the same 404 as a missing group so ids can't be probed.
    if group is None or user_id not in group.member_ids:
        raise NotFound("Group not found")
    return group


def add_member(db: Database, group: Group, identifier: str) -> Group:
    invitee = find_user(db, identifier)
    if invitee is None:
        raise NotFound("No SplitEasy user with that email or username")
    if invitee.id in group.member_ids:
        raise Conflict(f"{invitee.username} is already in this group")

    db.add_group_member(group.id, invitee.id)
    return db.get_group(group.id)  # type: ignore[return-value]


def group_members(db: Database, group: Group) -> list[User]:
    return [user for uid in group.member_ids if (user := db.get_user(uid)) is not None]


# ---- Expenses ----


def create_expense(db: Database, group: Group, creator: User, data: ExpenseCreateIn) -> Expense:
    description = data.description.strip()
    if not description:
        raise Unprocessable("Description is required")
    if data.amount_cents <= 0:
        raise Unprocessable("Amount must be greater than zero")
    if data.paid_by_id not in group.member_ids:
        raise Unprocessable("The payer must be a group member")

    seen: set[str] = set()
    for split in data.splits:
        if split.user_id not in group.member_ids:
            raise Unprocessable("Everyone in the split must be a group member")
        if split.user_id in seen:
            raise Unprocessable("Each member can appear in the split only once")
        if split.value < 0:
            raise Unprocessable("Split values cannot be negative")
        seen.add(split.user_id)

    active = [s for s in data.splits if s.value > 0]
    if not active:
        raise Unprocessable("Split the expense between at least one member")

    if data.split_type == "amount":
        if any(not s.value.is_integer() for s in active):
            raise Unprocessable("Split amounts must be whole cents")
        total = sum(int(s.value) for s in active)
        if total != data.amount_cents:
            raise Unprocessable(
                f"Splits add up to {format_cents(total)}, but the expense is {format_cents(data.amount_cents)}"
            )
        splits = [ExpenseSplit(user_id=s.user_id, amount_cents=int(s.value)) for s in active]
    else:
        hundredths = []
        for s in active:
            scaled = s.value * 100
            if abs(scaled - round(scaled)) > 1e-6:
                raise Unprocessable("Percentages can have at most 2 decimal places")
            hundredths.append(round(scaled))
        total = sum(hundredths)
        if total != FULL_PERCENT_HUNDREDTHS:
            raise Unprocessable(f"Percentages add up to {total / 100:g}%, not 100%")
        amounts = allocate_proportional(data.amount_cents, hundredths)
        splits = [
            ExpenseSplit(user_id=s.user_id, amount_cents=amount, percent=h / 100)
            for s, amount, h in zip(active, amounts, hundredths)
        ]

    expense = Expense(
        id=new_id(),
        group_id=group.id,
        description=description,
        amount_cents=data.amount_cents,
        paid_by_id=data.paid_by_id,
        split_type=data.split_type,
        splits=splits,
        created_by_id=creator.id,
        created_at=utcnow(),
    )
    db.add_expense(expense)
    return expense


# ---- Balances & settlements ----


def net_balances(db: Database, group: Group) -> dict[str, int]:
    return compute_net_balances(group.member_ids, db.list_expenses(group.id), db.list_settlements(group.id))


def create_settlement(db: Database, group: Group, creator: User, data: SettlementCreateIn) -> Settlement:
    if data.from_user_id not in group.member_ids or data.to_user_id not in group.member_ids:
        raise Unprocessable("Both people must be group members")
    if data.from_user_id == data.to_user_id:
        raise Unprocessable("Payer and recipient must be different people")
    if data.amount_cents <= 0:
        raise Unprocessable("Amount must be greater than zero")

    settlement = Settlement(
        id=new_id(),
        group_id=group.id,
        from_user_id=data.from_user_id,
        to_user_id=data.to_user_id,
        amount_cents=data.amount_cents,
        created_by_id=creator.id,
        created_at=utcnow(),
    )
    db.add_settlement(settlement)
    return settlement
