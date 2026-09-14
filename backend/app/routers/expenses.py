from fastapi import APIRouter, status

from app import services
from app.deps import CurrentUserDep, DbDep, MemberGroupDep
from app.schemas import ExpenseCreateIn, ExpenseOut

router = APIRouter(prefix="/groups/{group_id}/expenses", tags=["expenses"])


@router.get("", response_model=list[ExpenseOut])
def list_expenses(group: MemberGroupDep, db: DbDep) -> list[ExpenseOut]:
    return [ExpenseOut.model_validate(e) for e in db.list_expenses(group.id)]


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(body: ExpenseCreateIn, group: MemberGroupDep, user: CurrentUserDep, db: DbDep) -> ExpenseOut:
    return ExpenseOut.model_validate(services.create_expense(db, group, user, body))
