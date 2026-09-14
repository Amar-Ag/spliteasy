from fastapi import APIRouter, status

from app import services
from app.database import Database
from app.deps import CurrentUserDep, DbDep, MemberGroupDep
from app.models import Group
from app.schemas import AddMemberIn, GroupCreateIn, GroupOut, GroupSummaryOut, UserOut

router = APIRouter(prefix="/groups", tags=["groups"])


def to_group_out(db: Database, group: Group) -> GroupOut:
    return GroupOut(
        id=group.id,
        name=group.name,
        members=[UserOut.model_validate(u) for u in services.group_members(db, group)],
        created_by_id=group.created_by_id,
        created_at=group.created_at,
    )


@router.get("", response_model=list[GroupSummaryOut])
def list_groups(user: CurrentUserDep, db: DbDep) -> list[GroupSummaryOut]:
    return [
        GroupSummaryOut(
            id=group.id,
            name=group.name,
            member_count=len(group.member_ids),
            my_balance_cents=services.net_balances(db, group).get(user.id, 0),
        )
        for group in db.list_groups_for_user(user.id)
    ]


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(body: GroupCreateIn, user: CurrentUserDep, db: DbDep) -> GroupOut:
    return to_group_out(db, services.create_group(db, user, body.name))


@router.get("/{group_id}", response_model=GroupOut)
def get_group(group: MemberGroupDep, db: DbDep) -> GroupOut:
    return to_group_out(db, group)


@router.post("/{group_id}/members", response_model=GroupOut)
def add_member(body: AddMemberIn, group: MemberGroupDep, db: DbDep) -> GroupOut:
    return to_group_out(db, services.add_member(db, group, body.identifier))
