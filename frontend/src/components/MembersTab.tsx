import { useState, type FormEvent } from 'react';
import { api } from '../api';
import { errorMessage } from '../apiError';
import type { Group } from '../types';
import type { People } from './people';

interface Props {
  group: Group;
  people: People;
  onChanged(): void;
}

export function MembersTab({ group, people, onChanged }: Props) {
  const [identifier, setIdentifier] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    try {
      const before = new Set(group.members.map((m) => m.id));
      const updated = await api.addMember(group.id, identifier);
      const added = updated.members.find((m) => !before.has(m.id));
      setSuccess(`${added?.username ?? 'They'} joined the group.`);
      setIdentifier('');
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <section>
        <h2>Members</h2>
        <ul className="card rows">
          {group.members.map((m) => (
            <li key={m.id} className="row member-row">
              <span className="avatar" aria-hidden>
                {m.username.charAt(0).toUpperCase()}
              </span>
              <div className="grow">
                <div>
                  {m.username} {m.id === people.currentUserId && <span className="tag">you</span>}
                </div>
                <div className="muted small">{m.email}</div>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Invite someone</h2>
        <form className="card inline-form" onSubmit={onSubmit}>
          <label className="field grow">
            <span>Email or username</span>
            <input value={identifier} onChange={(e) => setIdentifier(e.target.value)} placeholder="friend@example.com" required />
            <small className="hint">They need a SplitEasy account and are added right away.</small>
          </label>
          <button className="btn btn-primary" disabled={submitting || !identifier.trim()}>
            {submitting ? 'Adding…' : 'Add to group'}
          </button>
          {error && <p className="error full-row">{error}</p>}
          {success && <p className="success full-row">{success}</p>}
        </form>
      </section>
    </>
  );
}
