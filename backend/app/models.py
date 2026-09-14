"""Domain records stored by the database layer. Money is always integer cents."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

SplitType = Literal["amount", "percent"]


def new_id() -> str:
    return uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class User:
    id: str
    email: str
    username: str
    password_hash: str
    created_at: datetime


@dataclass
class Group:
    id: str
    name: str
    created_by_id: str
    created_at: datetime
    member_ids: list[str] = field(default_factory=list)


@dataclass
class ExpenseSplit:
    user_id: str
    amount_cents: int
    percent: float | None = None


@dataclass
class Expense:
    id: str
    group_id: str
    description: str
    amount_cents: int
    paid_by_id: str
    split_type: SplitType
    splits: list[ExpenseSplit]
    created_by_id: str
    created_at: datetime


@dataclass
class Settlement:
    id: str
    group_id: str
    from_user_id: str
    to_user_id: str
    amount_cents: int
    created_by_id: str
    created_at: datetime
