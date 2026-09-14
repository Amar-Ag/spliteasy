from fastapi import APIRouter, status

from app import services
from app.deps import CurrentUserDep, DbDep, MemberGroupDep
from app.money import simplify_debts
from app.schemas import BalancesOut, NetBalanceOut, SettlementCreateIn, SettlementOut, TransferOut

router = APIRouter(prefix="/groups/{group_id}", tags=["balances & settlements"])


@router.get("/balances", response_model=BalancesOut)
def get_balances(group: MemberGroupDep, db: DbDep) -> BalancesOut:
    net = services.net_balances(db, group)
    return BalancesOut(
        net=[NetBalanceOut(user_id=uid, amount_cents=net.get(uid, 0)) for uid in group.member_ids],
        transfers=[TransferOut.model_validate(t) for t in simplify_debts(net)],
    )


@router.get("/settlements", response_model=list[SettlementOut])
def list_settlements(group: MemberGroupDep, db: DbDep) -> list[SettlementOut]:
    return [SettlementOut.model_validate(s) for s in db.list_settlements(group.id)]


@router.post("/settlements", response_model=SettlementOut, status_code=status.HTTP_201_CREATED)
def create_settlement(body: SettlementCreateIn, group: MemberGroupDep, user: CurrentUserDep, db: DbDep) -> SettlementOut:
    return SettlementOut.model_validate(services.create_settlement(db, group, user, body))
