import { useState, type FormEvent } from 'react';
import { api } from '../api';
import { errorMessage } from '../apiError';
import { centsToInput, parseDollars } from '../lib/format';
import type { NewSettlement, User } from '../types';
import type { People } from './people';

interface Props {
  groupId: string;
  members: User[];
  people: People;
  initial: Partial<NewSettlement>;
  onRecorded(): void;
  onCancel(): void;
}

export function SettleForm({ groupId, members, people, initial, onRecorded, onCancel }: Props) {
  const defaultFrom = initial.fromUserId ?? people.currentUserId;
  const [fromUserId, setFromUserId] = useState(defaultFrom);
  const [toUserId, setToUserId] = useState(initial.toUserId ?? members.find((m) => m.id !== defaultFrom)?.id ?? '');
  const [amount, setAmount] = useState(initial.amountCents ? centsToInput(initial.amountCents) : '');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const cents = parseDollars(amount);
  const samePerson = fromUserId === toUserId;
  const canSubmit = !samePerson && toUserId !== '' && cents !== null && cents > 0;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit || cents === null) return;
    setError(null);
    setSubmitting(true);
    try {
      await api.createSettlement(groupId, { fromUserId, toUserId, amountCents: cents });
      onRecorded();
    } catch (err) {
      setError(errorMessage(err));
      setSubmitting(false);
    }
  }

  const options = members.map((m) => (
    <option key={m.id} value={m.id}>
      {people.subject(m.id)}
    </option>
  ));

  return (
    <form className="card form" onSubmit={onSubmit}>
      <h3>Record a payment</h3>
      <div className="form-row settle-row">
        <label className="field">
          <span>Who paid</span>
          <select value={fromUserId} onChange={(e) => setFromUserId(e.target.value)}>
            {options}
          </select>
        </label>
        <span className="settle-arrow" aria-hidden>→</span>
        <label className="field">
          <span>Paid to</span>
          <select value={toUserId} onChange={(e) => setToUserId(e.target.value)}>
            {options}
          </select>
        </label>
        <label className="field amount-field">
          <span>Amount ($)</span>
          <input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" placeholder="0.00" aria-invalid={amount !== '' && cents === null} required autoFocus />
        </label>
      </div>
      {samePerson && <p className="error">Pick two different people.</p>}
      {error && <p className="error" role="alert">{error}</p>}
      <div className="form-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Cancel
        </button>
        <button className="btn btn-primary" disabled={!canSubmit || submitting}>
          {submitting ? 'Saving…' : 'Record payment'}
        </button>
      </div>
    </form>
  );
}
