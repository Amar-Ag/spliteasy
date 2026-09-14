"""Pure money math: splitting amounts and working out who owes whom. All values are integer cents."""

from collections.abc import Iterable
from dataclasses import dataclass

from app.models import Expense, Settlement


@dataclass(frozen=True)
class Transfer:
    from_user_id: str
    to_user_id: str
    amount_cents: int


def allocate_proportional(total: int, weights: list[int]) -> list[int]:
    """Split `total` into integer parts proportional to `weights`, summing exactly to `total`.

    Leftover units go to the parts with the largest remainder (earlier index wins ties),
    which matches the frontend's preview.
    """
    weight_sum = sum(weights)
    if weight_sum <= 0:
        return [0] * len(weights)

    parts = [total * w // weight_sum for w in weights]
    remainders = [total * w % weight_sum for w in weights]
    leftover = total - sum(parts)
    order = sorted(range(len(weights)), key=lambda i: (-remainders[i], i))
    for i in order[:leftover]:
        parts[i] += 1
    return parts


def compute_net_balances(
    member_ids: Iterable[str],
    expenses: Iterable[Expense],
    settlements: Iterable[Settlement],
) -> dict[str, int]:
    """Positive: the group owes this person. Negative: they owe the group."""
    net = {member_id: 0 for member_id in member_ids}

    def add(user_id: str, cents: int) -> None:
        net[user_id] = net.get(user_id, 0) + cents

    for expense in expenses:
        add(expense.paid_by_id, expense.amount_cents)
        for split in expense.splits:
            add(split.user_id, -split.amount_cents)
    for settlement in settlements:
        add(settlement.from_user_id, settlement.amount_cents)
        add(settlement.to_user_id, -settlement.amount_cents)
    return net


def simplify_debts(net: dict[str, int]) -> list[Transfer]:
    """Greedily pair the largest debtors with the largest creditors to keep the number of payments small."""
    creditors = sorted(([uid, c] for uid, c in net.items() if c > 0), key=lambda x: -x[1])
    debtors = sorted(([uid, -c] for uid, c in net.items() if c < 0), key=lambda x: -x[1])

    transfers: list[Transfer] = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        debtor, creditor = debtors[i], creditors[j]
        cents = min(debtor[1], creditor[1])
        transfers.append(Transfer(from_user_id=debtor[0], to_user_id=creditor[0], amount_cents=cents))
        debtor[1] -= cents
        creditor[1] -= cents
        if debtor[1] == 0:
            i += 1
        if creditor[1] == 0:
            j += 1
    return transfers
