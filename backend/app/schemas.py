"""Request/response bodies. JSON uses camelCase to match frontend/src/types.ts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.models import SplitType


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


# ---- Auth ----


class UserOut(ApiModel):
    id: str
    email: str
    username: str


class RegisterIn(ApiModel):
    email: str
    username: str
    password: str


class LoginIn(ApiModel):
    identifier: str  # email or username
    password: str


class AuthOut(ApiModel):
    token: str
    user: UserOut


# ---- Groups ----


class GroupCreateIn(ApiModel):
    name: str


class AddMemberIn(ApiModel):
    identifier: str  # email or username


class GroupOut(ApiModel):
    id: str
    name: str
    members: list[UserOut]
    created_by_id: str
    created_at: datetime


class GroupSummaryOut(ApiModel):
    id: str
    name: str
    member_count: int
    my_balance_cents: int


# ---- Expenses ----


class SplitIn(ApiModel):
    user_id: str
    value: float  # cents for 'amount' splits, percentage (0-100) for 'percent' splits


class ExpenseCreateIn(ApiModel):
    description: str
    amount_cents: int
    paid_by_id: str
    split_type: SplitType
    splits: list[SplitIn]


class ExpenseSplitOut(ApiModel):
    user_id: str
    amount_cents: int
    percent: float | None = None


class ExpenseOut(ApiModel):
    id: str
    group_id: str
    description: str
    amount_cents: int
    paid_by_id: str
    split_type: SplitType
    splits: list[ExpenseSplitOut]
    created_by_id: str
    created_at: datetime


# ---- Balances & settlements ----


class SettlementCreateIn(ApiModel):
    from_user_id: str
    to_user_id: str
    amount_cents: int


class SettlementOut(ApiModel):
    id: str
    group_id: str
    from_user_id: str
    to_user_id: str
    amount_cents: int
    created_by_id: str
    created_at: datetime


class NetBalanceOut(ApiModel):
    user_id: str
    amount_cents: int


class TransferOut(ApiModel):
    from_user_id: str
    to_user_id: str
    amount_cents: int


class BalancesOut(ApiModel):
    net: list[NetBalanceOut]
    transfers: list[TransferOut]
