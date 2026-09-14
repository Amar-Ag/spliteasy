"""In-memory implementation of `Database`. Data is lost when the process stops."""

import copy
import threading
from datetime import datetime

from app.models import Expense, Group, Settlement, User, utcnow


class MockDatabase:
    def __init__(self) -> None:
        # Dicts keep insertion order, which doubles as creation order.
        self._users: dict[str, User] = {}
        self._groups: dict[str, Group] = {}
        self._expenses: dict[str, Expense] = {}
        self._settlements: dict[str, Settlement] = {}
        self._revoked_tokens: dict[str, datetime] = {}
        self._lock = threading.RLock()

    # Records are copied in and out so callers can't mutate stored state,
    # matching how a real database behaves.

    # ---- Users ----

    def add_user(self, user: User) -> None:
        with self._lock:
            self._users[user.id] = copy.deepcopy(user)

    def get_user(self, user_id: str) -> User | None:
        with self._lock:
            return copy.deepcopy(self._users.get(user_id))

    def get_user_by_email(self, email: str) -> User | None:
        needle = email.lower()
        with self._lock:
            return copy.deepcopy(next((u for u in self._users.values() if u.email.lower() == needle), None))

    def get_user_by_username(self, username: str) -> User | None:
        needle = username.lower()
        with self._lock:
            return copy.deepcopy(next((u for u in self._users.values() if u.username.lower() == needle), None))

    # ---- Groups ----

    def add_group(self, group: Group) -> None:
        with self._lock:
            self._groups[group.id] = copy.deepcopy(group)

    def get_group(self, group_id: str) -> Group | None:
        with self._lock:
            return copy.deepcopy(self._groups.get(group_id))

    def list_groups_for_user(self, user_id: str) -> list[Group]:
        with self._lock:
            return [copy.deepcopy(g) for g in reversed(self._groups.values()) if user_id in g.member_ids]

    def add_group_member(self, group_id: str, user_id: str) -> None:
        with self._lock:
            group = self._groups[group_id]
            if user_id not in group.member_ids:
                group.member_ids.append(user_id)

    # ---- Expenses ----

    def add_expense(self, expense: Expense) -> None:
        with self._lock:
            self._expenses[expense.id] = copy.deepcopy(expense)

    def list_expenses(self, group_id: str) -> list[Expense]:
        with self._lock:
            return [copy.deepcopy(e) for e in reversed(self._expenses.values()) if e.group_id == group_id]

    # ---- Settlements ----

    def add_settlement(self, settlement: Settlement) -> None:
        with self._lock:
            self._settlements[settlement.id] = copy.deepcopy(settlement)

    def list_settlements(self, group_id: str) -> list[Settlement]:
        with self._lock:
            return [copy.deepcopy(s) for s in reversed(self._settlements.values()) if s.group_id == group_id]

    # ---- Revoked tokens ----

    def revoke_token(self, jti: str, expires_at: datetime) -> None:
        with self._lock:
            now = utcnow()
            # Expired tokens are rejected anyway, so drop them to keep the set small.
            self._revoked_tokens = {k: v for k, v in self._revoked_tokens.items() if v > now}
            self._revoked_tokens[jti] = expires_at

    def is_token_revoked(self, jti: str) -> bool:
        with self._lock:
            return jti in self._revoked_tokens
