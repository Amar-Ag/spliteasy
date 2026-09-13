import { useState } from 'react';
import { formatCents, formatDate } from '../lib/format';
import type { Balances, Group, NewSettlement, Settlement } from '../types';
import type { People } from './people';
import { SettleForm } from './SettleForm';

interface Props {
  group: Group;
  balances: Balances;
  settlements: Settlement[];
  people: People;
  onChanged(): void;
}

export function BalancesTab({ group, balances, settlements, people, onChanged }: Props) {
  const [draft, setDraft] = useState<Partial<NewSettlement> | null>(null);
  const [draftKey, setDraftKey] = useState(0);

  function openSettle(initial: Partial<NewSettlement>) {
    setDraft(initial);
    setDraftKey((k) => k + 1); // remount the form with fresh defaults
  }

  return (
    <>
      <section>
        <div className="section-header">
          <h2>Who owes whom</h2>
          {group.members.length > 1 && (
            <button className="btn btn-secondary" onClick={() => openSettle({})}>
              Record a payment
            </button>
          )}
        </div>

        {draft && (
          <SettleForm
            key={draftKey}
            groupId={group.id}
            members={group.members}
            people={people}
            initial={draft}
            onCancel={() => setDraft(null)}
            onRecorded={() => {
              setDraft(null);
              onChanged();
            }}
          />
        )}

        {balances.transfers.length === 0 ? (
          <div className="empty">Everyone is squared up.</div>
        ) : (
          <ul className="list">
            {balances.transfers.map((t) => (
              <li key={`${t.fromUserId}-${t.toUserId}`} className="card transfer">
                <span>
                  <strong>{people.subject(t.fromUserId)}</strong> {t.fromUserId === people.currentUserId ? 'owe' : 'owes'}{' '}
                  <strong>{people.object(t.toUserId)}</strong>
                </span>
                <span className="transfer-amount">{formatCents(t.amountCents)}</span>
                <button className="btn btn-small btn-secondary" onClick={() => openSettle(t)}>
                  Settle up
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2>Net balances</h2>
        <ul className="card rows">
          {balances.net.map((n) => (
            <li key={n.userId} className="row">
              <span>{people.subject(n.userId)}</span>
              {n.amountCents > 0 ? (
                <span className="positive">gets back {formatCents(n.amountCents)}</span>
              ) : n.amountCents < 0 ? (
                <span className="negative">
                  {n.userId === people.currentUserId ? 'owe' : 'owes'} {formatCents(-n.amountCents)}
                </span>
              ) : (
                <span className="muted">settled up</span>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Payment history</h2>
        {settlements.length === 0 ? (
          <p className="muted">No payments recorded yet.</p>
        ) : (
          <ul className="card rows">
            {settlements.map((s) => (
              <li key={s.id} className="row">
                <span>
                  {people.subject(s.fromUserId)} paid {people.object(s.toUserId)}
                  <span className="muted small"> · {formatDate(s.createdAt)}</span>
                </span>
                <span>{formatCents(s.amountCents)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
