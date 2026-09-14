"""Storage interface used by the rest of the app. `SqlDatabase` (app/sql_database.py) implements it.

Everything outside the storage layer depends only on this protocol and the dataclasses in
app/models.py, so the backing database can change without touching services or routes.
"""

from datetime import datetime
from typing import Protocol

from app.models import Expense, Group, Settlement, User


class DuplicateError(Exception):
    """A record would violate a uniqueness rule (e.g. an email or username is already taken)."""


class Database(Protocol):
    # Users
    def add_user(self, user: User) -> None:
        """Raises `DuplicateError` if the email or username (case-insensitive) is taken."""
        ...

    def get_user(self, user_id: str) -> User | None: ...
    def get_user_by_email(self, email: str) -> User | None:
        """Case-insensitive match."""
        ...

    def get_user_by_username(self, username: str) -> User | None:
        """Case-insensitive match."""
        ...

    # Groups
    def add_group(self, group: Group) -> None: ...
    def get_group(self, group_id: str) -> Group | None: ...
    def list_groups_for_user(self, user_id: str) -> list[Group]:
        """Newest first."""
        ...

    def add_group_member(self, group_id: str, user_id: str) -> None:
        """Appends to the member list; a no-op if they're already a member."""
        ...

    # Expenses
    def add_expense(self, expense: Expense) -> None: ...
    def list_expenses(self, group_id: str) -> list[Expense]:
        """Newest first."""
        ...

    # Settlements
    def add_settlement(self, settlement: Settlement) -> None: ...
    def list_settlements(self, group_id: str) -> list[Settlement]:
        """Newest first."""
        ...

    # Revoked JWTs (logout)
    def revoke_token(self, jti: str, expires_at: datetime) -> None: ...
    def is_token_revoked(self, jti: str) -> bool: ...
