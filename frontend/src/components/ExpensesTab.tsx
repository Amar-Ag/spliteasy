import { useState } from 'react';
import { formatCents, formatDate } from '../lib/format';
import type { Expense, Group } from '../types';
import { AddExpenseForm } from './AddExpenseForm';
import type { People } from './people';

interface Props {
  group: Group;
  expenses: Expense[];
  people: People;
  onChanged(): void;
  onInvite(): void;
}

export function ExpensesTab({ group, expenses, people, onChanged, onInvite }: Props) {
  const [adding, setAdding] = useState(false);

  return (
    <section>
      <div className="section-header">
        <h2>Expense history</h2>
        {!adding && (
          <button className="btn btn-primary" onClick={() => setAdding(true)}>
            + Add expense
          </button>
        )}
      </div>

      {group.members.length === 1 && (
        <p className="notice">
          You're the only member so far.{' '}
          <button className="btn-link" onClick={onInvite}>
            Invite people
          </button>{' '}
          to split costs with them.
        </p>
      )}

      {adding && (
        <AddExpenseForm
          groupId={group.id}
          members={group.members}
          people={people}
          onCancel={() => setAdding(false)}
          onCreated={() => {
            setAdding(false);
            onChanged();
          }}
        />
      )}

      {expenses.length === 0 ? (
        <div className="empty">No expenses yet.</div>
      ) : (
        <ul className="list">
          {expenses.map((e) => (
            <ExpenseItem key={e.id} expense={e} people={people} />
          ))}
        </ul>
      )}
    </section>
  );
}

function ExpenseItem({ expense, people }: { expense: Expense; people: People }) {
  const myShare = expense.splits.find((s) => s.userId === people.currentUserId)?.amountCents ?? 0;
  const paidByMe = expense.paidById === people.currentUserId;
  const impact = (paidByMe ? expense.amountCents : 0) - myShare;

  return (
    <li className="card expense">
      <details>
        <summary>
          <div className="expense-main">
            <span className="expense-title">{expense.description}</span>
            <span className="muted small">
              {people.subject(expense.paidById)} paid {formatCents(expense.amountCents)} · {formatDate(expense.createdAt)}
            </span>
          </div>
          <div className="expense-impact">
            {impact > 0 ? (
              <span className="positive">you lent {formatCents(impact)}</span>
            ) : impact < 0 ? (
              <span className="negative">you borrowed {formatCents(-impact)}</span>
            ) : (
              <span className="muted">{myShare > 0 ? 'your own share' : 'not involved'}</span>
            )}
          </div>
        </summary>
        <table className="split-table">
          <thead>
            <tr>
              <th>Member</th>
              {expense.splitType === 'percent' && <th className="num">Share</th>}
              <th className="num">Owes</th>
            </tr>
          </thead>
          <tbody>
            {expense.splits.map((s) => (
              <tr key={s.userId}>
                <td>{people.subject(s.userId)}</td>
                {expense.splitType === 'percent' && <td className="num">{s.percent}%</td>}
                <td className="num">{formatCents(s.amountCents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </li>
  );
}
