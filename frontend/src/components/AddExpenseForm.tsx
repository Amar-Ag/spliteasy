import { useState, type FormEvent } from 'react';
import { api } from '../api';
import { errorMessage } from '../apiError';
import { centsToInput, formatCents, formatPercentHundredths, parseDollars, parsePercent } from '../lib/format';
import { allocateProportional, splitEvenly } from '../lib/split';
import type { SplitType, User } from '../types';
import type { People } from './people';

interface Props {
  groupId: string;
  members: User[];
  people: People;
  onCreated(): void;
  onCancel(): void;
}

const FULL_PERCENT = 10000; // hundredths of a percent

function evenValues(splitType: SplitType, totalCents: number | null, ids: string[]): Record<string, string> {
  if (ids.length === 0) return {};
  if (splitType === 'percent') {
    const parts = splitEvenly(FULL_PERCENT, ids.length);
    return Object.fromEntries(ids.map((id, i) => [id, formatPercentHundredths(parts[i])]));
  }
  if (totalCents === null) return Object.fromEntries(ids.map((id) => [id, '']));
  const parts = splitEvenly(totalCents, ids.length);
  return Object.fromEntries(ids.map((id, i) => [id, centsToInput(parts[i])]));
}

export function AddExpenseForm({ groupId, members, people, onCreated, onCancel }: Props) {
  const [description, setDescription] = useState('');
  const [amount, setAmount] = useState('');
  const [paidById, setPaidById] = useState(people.currentUserId);
  const [splitType, setSplitType] = useState<SplitType>('amount');
  const [included, setIncluded] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(members.map((m) => [m.id, true])),
  );
  // While `customized` is false the split tracks an even split of the current total.
  const [customized, setCustomized] = useState(false);
  const [customValues, setCustomValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const totalCents = parseDollars(amount);
  const includedIds = members.filter((m) => included[m.id]).map((m) => m.id);
  const values = customized ? customValues : evenValues(splitType, totalCents, includedIds);
  const parse = splitType === 'amount' ? parseDollars : parsePercent;

  const rows = members.map((m) => {
    const raw = values[m.id] ?? '';
    const parsed = raw.trim() === '' ? 0 : parse(raw);
    return { member: m, isIncluded: !!included[m.id], raw, parsed };
  });
  const active = rows.filter((r) => r.isIncluded);
  const hasInvalid = active.some((r) => r.parsed === null);
  const assigned = active.reduce((sum, r) => sum + (r.parsed ?? 0), 0);
  const target = splitType === 'amount' ? totalCents : FULL_PERCENT;
  const remaining = target === null ? null : target - assigned;

  const percentPreview: Record<string, number> = {};
  if (splitType === 'percent' && totalCents !== null && !hasInvalid && assigned === FULL_PERCENT) {
    const amounts = allocateProportional(totalCents, active.map((r) => r.parsed ?? 0));
    active.forEach((r, i) => (percentPreview[r.member.id] = amounts[i]));
  }

  const canSubmit =
    description.trim() !== '' && totalCents !== null && totalCents > 0 && active.length > 0 && !hasInvalid && remaining === 0;

  let status: { text: string; ok: boolean };
  if (active.length === 0) status = { text: 'Pick at least one person to split with.', ok: false };
  else if (hasInvalid) status = { text: splitType === 'amount' ? 'Use amounts like 12.50.' : 'Use percentages like 33.33.', ok: false };
  else if (remaining === null) status = { text: 'Enter the total amount first.', ok: false };
  else if (remaining === 0) status = { text: 'Split adds up.', ok: true };
  else {
    const fmt = (v: number) => (splitType === 'amount' ? formatCents(v) : `${formatPercentHundredths(v)}%`);
    status = { text: remaining > 0 ? `${fmt(remaining)} left to assign` : `${fmt(-remaining)} over the total`, ok: false };
  }

  function editValue(userId: string, value: string) {
    setCustomValues({ ...values, [userId]: value });
    setCustomized(true);
  }

  function changeSplitType(next: SplitType) {
    setSplitType(next);
    setCustomized(false);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit || totalCents === null) return;
    setError(null);
    setSubmitting(true);
    try {
      await api.createExpense(groupId, {
        description,
        amountCents: totalCents,
        paidById,
        splitType,
        splits: active.map((r) => ({
          userId: r.member.id,
          value: splitType === 'amount' ? (r.parsed ?? 0) : (r.parsed ?? 0) / 100,
        })),
      });
      onCreated();
    } catch (err) {
      setError(errorMessage(err));
      setSubmitting(false);
    }
  }

  return (
    <form className="card form" onSubmit={onSubmit}>
      <h3>New expense</h3>
      <div className="form-row">
        <label className="field grow">
          <span>Description</span>
          <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Dinner, groceries, rent…" required autoFocus />
        </label>
        <label className="field amount-field">
          <span>Total ($)</span>
          <input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" placeholder="0.00" aria-invalid={amount !== '' && totalCents === null} required />
        </label>
        <label className="field">
          <span>Paid by</span>
          <select value={paidById} onChange={(e) => setPaidById(e.target.value)}>
            {members.map((m) => (
              <option key={m.id} value={m.id}>
                {people.subject(m.id)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="split-header">
        <span className="field-label">Split</span>
        <div className="segmented">
          <button type="button" className={splitType === 'amount' ? 'active' : ''} onClick={() => changeSplitType('amount')}>
            By amount
          </button>
          <button type="button" className={splitType === 'percent' ? 'active' : ''} onClick={() => changeSplitType('percent')}>
            By percentage
          </button>
        </div>
        <button type="button" className="btn-link" onClick={() => setCustomized(false)} disabled={!customized}>
          Split equally
        </button>
      </div>

      <ul className="split-rows">
        {rows.map((r) => (
          <li key={r.member.id} className={r.isIncluded ? 'split-row' : 'split-row excluded'}>
            <label className="checkbox">
              <input type="checkbox" checked={r.isIncluded} onChange={(e) => setIncluded({ ...included, [r.member.id]: e.target.checked })} />
              {people.subject(r.member.id)}
            </label>
            <div className="affix-input">
              {splitType === 'amount' && <span>$</span>}
              <input
                value={r.isIncluded ? r.raw : ''}
                onChange={(e) => editValue(r.member.id, e.target.value)}
                disabled={!r.isIncluded}
                inputMode="decimal"
                placeholder="0"
                aria-label={`${r.member.username} share`}
                aria-invalid={r.isIncluded && r.parsed === null}
              />
              {splitType === 'percent' && <span>%</span>}
            </div>
            {splitType === 'percent' && (
              <span className="muted small preview">
                {r.isIncluded && percentPreview[r.member.id] !== undefined ? formatCents(percentPreview[r.member.id]) : '—'}
              </span>
            )}
          </li>
        ))}
      </ul>

      <p className={status.ok ? 'split-status ok' : 'split-status'}>{status.text}</p>
      {error && <p className="error" role="alert">{error}</p>}

      <div className="form-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Cancel
        </button>
        <button className="btn btn-primary" disabled={!canSubmit || submitting}>
          {submitting ? 'Saving…' : 'Add expense'}
        </button>
      </div>
    </form>
  );
}
