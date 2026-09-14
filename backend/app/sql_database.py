"""SQLAlchemy implementation of the `Database` protocol.

Works with any SQLAlchemy-supported database; SQLite is the default. Tables map to the domain
dataclasses in app/models.py, and every method converts rows to/from those dataclasses so no
ORM objects leak out of this module.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Engine,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    delete,
    event,
    select,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, selectinload, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

from app.database import DuplicateError
from app.models import Expense, ExpenseSplit, Group, Settlement, User, utcnow

ID = String(32)


class UTCDateTime(TypeDecorator[datetime]):
    """Stores timezone-aware datetimes as naive UTC (portable across databases) and returns them as aware UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Datetimes must be timezone-aware")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    pass


# Tables with a user-visible order use an auto-increment `seq` primary key as a tie-breaker, so
# records created within the same clock tick still come back in insertion order.


class UserRow(Base):
    __tablename__ = "users"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(ID, unique=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)  # stored lowercase
    username: Mapped[str] = mapped_column(String(50))
    username_key: Mapped[str] = mapped_column(String(50), unique=True)  # lowercase, enforces case-insensitive uniqueness
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())


class GroupRow(Base):
    __tablename__ = "groups"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(ID, unique=True)
    name: Mapped[str] = mapped_column(String(100))
    created_by_id: Mapped[str] = mapped_column(ID, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)

    members: Mapped[list["GroupMemberRow"]] = relationship(
        order_by="GroupMemberRow.seq", cascade="all, delete-orphan", lazy="raise"
    )


class GroupMemberRow(Base):
    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id"),)

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[str] = mapped_column(ID, ForeignKey("groups.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ID, ForeignKey("users.id"), index=True)


class ExpenseRow(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="expense_amount_positive"),
        CheckConstraint("split_type IN ('amount', 'percent')", name="expense_split_type_valid"),
    )

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(ID, unique=True)
    group_id: Mapped[str] = mapped_column(ID, ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    description: Mapped[str] = mapped_column(String(200))
    amount_cents: Mapped[int] = mapped_column(Integer)
    paid_by_id: Mapped[str] = mapped_column(ID, ForeignKey("users.id"))
    split_type: Mapped[str] = mapped_column(String(10))
    created_by_id: Mapped[str] = mapped_column(ID, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())

    splits: Mapped[list["ExpenseSplitRow"]] = relationship(
        order_by="ExpenseSplitRow.seq", cascade="all, delete-orphan", lazy="raise"
    )


class ExpenseSplitRow(Base):
    __tablename__ = "expense_splits"
    __table_args__ = (
        UniqueConstraint("expense_id", "user_id"),
        CheckConstraint("amount_cents >= 0", name="split_amount_non_negative"),
    )

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    expense_id: Mapped[str] = mapped_column(ID, ForeignKey("expenses.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ID, ForeignKey("users.id"))
    amount_cents: Mapped[int] = mapped_column(Integer)
    percent: Mapped[float | None] = mapped_column(Float, nullable=True)


class SettlementRow(Base):
    __tablename__ = "settlements"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="settlement_amount_positive"),
        CheckConstraint("from_user_id <> to_user_id", name="settlement_distinct_people"),
    )

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(ID, unique=True)
    group_id: Mapped[str] = mapped_column(ID, ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    from_user_id: Mapped[str] = mapped_column(ID, ForeignKey("users.id"))
    to_user_id: Mapped[str] = mapped_column(ID, ForeignKey("users.id"))
    amount_cents: Mapped[int] = mapped_column(Integer)
    created_by_id: Mapped[str] = mapped_column(ID, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())


class RevokedTokenRow(Base):
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


# ---- Row <-> domain conversion ----


def _user(row: UserRow) -> User:
    return User(id=row.id, email=row.email, username=row.username, password_hash=row.password_hash, created_at=row.created_at)


def _group(row: GroupRow) -> Group:
    return Group(
        id=row.id,
        name=row.name,
        created_by_id=row.created_by_id,
        created_at=row.created_at,
        member_ids=[m.user_id for m in row.members],
    )


def _expense(row: ExpenseRow) -> Expense:
    return Expense(
        id=row.id,
        group_id=row.group_id,
        description=row.description,
        amount_cents=row.amount_cents,
        paid_by_id=row.paid_by_id,
        split_type=row.split_type,  # type: ignore[arg-type]  # guarded by a CHECK constraint
        splits=[ExpenseSplit(user_id=s.user_id, amount_cents=s.amount_cents, percent=s.percent) for s in row.splits],
        created_by_id=row.created_by_id,
        created_at=row.created_at,
    )


def _settlement(row: SettlementRow) -> Settlement:
    return Settlement(
        id=row.id,
        group_id=row.group_id,
        from_user_id=row.from_user_id,
        to_user_id=row.to_user_id,
        amount_cents=row.amount_cents,
        created_by_id=row.created_by_id,
        created_at=row.created_at,
    )


# ---- Engine ----


def create_db_engine(url: str) -> Engine:
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        return create_engine(url, pool_pre_ping=True)

    kwargs: dict = {"connect_args": {"check_same_thread": False}}  # FastAPI runs sync endpoints in a threadpool
    if parsed.database in (None, "", ":memory:"):
        kwargs["poolclass"] = StaticPool  # one shared connection, otherwise each connection gets its own empty DB
    engine = create_engine(url, **kwargs)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


class SqlDatabase:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._sessionmaker = sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, url: str) -> "SqlDatabase":
        return cls(create_db_engine(url))

    def create_schema(self) -> None:
        """Create any missing tables. Existing tables and data are left alone."""
        Base.metadata.create_all(self._engine)

    def close(self) -> None:
        self._engine.dispose()

    @contextmanager
    def _session(self) -> Iterator[Session]:
        """One transaction per call: committed on success, rolled back on error."""
        with self._sessionmaker.begin() as session:
            yield session

    # ---- Users ----

    def add_user(self, user: User) -> None:
        try:
            with self._session() as session:
                session.add(
                    UserRow(
                        id=user.id,
                        email=user.email.lower(),
                        username=user.username,
                        username_key=user.username.lower(),
                        password_hash=user.password_hash,
                        created_at=user.created_at,
                    )
                )
        except IntegrityError as exc:
            raise DuplicateError("A user with that email or username already exists") from exc

    def get_user(self, user_id: str) -> User | None:
        with self._session() as session:
            row = session.scalar(select(UserRow).where(UserRow.id == user_id))
            return _user(row) if row else None

    def get_user_by_email(self, email: str) -> User | None:
        with self._session() as session:
            row = session.scalar(select(UserRow).where(UserRow.email == email.strip().lower()))
            return _user(row) if row else None

    def get_user_by_username(self, username: str) -> User | None:
        with self._session() as session:
            row = session.scalar(select(UserRow).where(UserRow.username_key == username.strip().lower()))
            return _user(row) if row else None

    # ---- Groups ----

    def add_group(self, group: Group) -> None:
        with self._session() as session:
            session.add(
                GroupRow(
                    id=group.id,
                    name=group.name,
                    created_by_id=group.created_by_id,
                    created_at=group.created_at,
                    members=[GroupMemberRow(user_id=uid) for uid in group.member_ids],
                )
            )

    def get_group(self, group_id: str) -> Group | None:
        with self._session() as session:
            row = session.scalar(select(GroupRow).where(GroupRow.id == group_id).options(selectinload(GroupRow.members)))
            return _group(row) if row else None

    def list_groups_for_user(self, user_id: str) -> list[Group]:
        with self._session() as session:
            rows = session.scalars(
                select(GroupRow)
                .join(GroupMemberRow, GroupMemberRow.group_id == GroupRow.id)
                .where(GroupMemberRow.user_id == user_id)
                .order_by(GroupRow.created_at.desc(), GroupRow.seq.desc())
                .options(selectinload(GroupRow.members))
            )
            return [_group(row) for row in rows]

    def add_group_member(self, group_id: str, user_id: str) -> None:
        with self._session() as session:
            exists = session.scalar(
                select(GroupMemberRow.seq).where(GroupMemberRow.group_id == group_id, GroupMemberRow.user_id == user_id)
            )
            if exists is None:
                session.add(GroupMemberRow(group_id=group_id, user_id=user_id))

    # ---- Expenses ----

    def add_expense(self, expense: Expense) -> None:
        with self._session() as session:
            session.add(
                ExpenseRow(
                    id=expense.id,
                    group_id=expense.group_id,
                    description=expense.description,
                    amount_cents=expense.amount_cents,
                    paid_by_id=expense.paid_by_id,
                    split_type=expense.split_type,
                    created_by_id=expense.created_by_id,
                    created_at=expense.created_at,
                    splits=[
                        ExpenseSplitRow(user_id=s.user_id, amount_cents=s.amount_cents, percent=s.percent)
                        for s in expense.splits
                    ],
                )
            )

    def list_expenses(self, group_id: str) -> list[Expense]:
        with self._session() as session:
            rows = session.scalars(
                select(ExpenseRow)
                .where(ExpenseRow.group_id == group_id)
                .order_by(ExpenseRow.created_at.desc(), ExpenseRow.seq.desc())
                .options(selectinload(ExpenseRow.splits))
            )
            return [_expense(row) for row in rows]

    # ---- Settlements ----

    def add_settlement(self, settlement: Settlement) -> None:
        with self._session() as session:
            session.add(
                SettlementRow(
                    id=settlement.id,
                    group_id=settlement.group_id,
                    from_user_id=settlement.from_user_id,
                    to_user_id=settlement.to_user_id,
                    amount_cents=settlement.amount_cents,
                    created_by_id=settlement.created_by_id,
                    created_at=settlement.created_at,
                )
            )

    def list_settlements(self, group_id: str) -> list[Settlement]:
        with self._session() as session:
            rows = session.scalars(
                select(SettlementRow)
                .where(SettlementRow.group_id == group_id)
                .order_by(SettlementRow.created_at.desc(), SettlementRow.seq.desc())
            )
            return [_settlement(row) for row in rows]

    # ---- Revoked tokens ----

    def revoke_token(self, jti: str, expires_at: datetime) -> None:
        with self._session() as session:
            # Expired tokens are rejected anyway, so clear them out while we're here.
            session.execute(delete(RevokedTokenRow).where(RevokedTokenRow.expires_at <= utcnow()))
            session.merge(RevokedTokenRow(jti=jti, expires_at=expires_at))

    def is_token_revoked(self, jti: str) -> bool:
        with self._session() as session:
            return session.get(RevokedTokenRow, jti) is not None
