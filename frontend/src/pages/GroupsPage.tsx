import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api';
import { errorMessage } from '../apiError';
import { BalanceLabel } from '../components/BalanceLabel';
import { useResource } from '../lib/useResource';

export function GroupsPage() {
  const { data: groups, error } = useResource(() => api.listGroups(), []);

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Your groups</h1>
          <p className="muted">Pick a group to add expenses or settle up.</p>
        </div>
      </div>

      <CreateGroupForm />

      {error && <p className="error">{error}</p>}
      {!groups ? (
        !error && <p className="muted">Loading groups…</p>
      ) : groups.length === 0 ? (
        <div className="empty">You're not in any groups yet. Create one above to get started.</div>
      ) : (
        <ul className="group-list">
          {groups.map((g) => (
            <li key={g.id}>
              <Link to={`/groups/${g.id}`} className="card group-card">
                <div>
                  <h2>{g.name}</h2>
                  <p className="muted small">
                    {g.memberCount} {g.memberCount === 1 ? 'member' : 'members'}
                  </p>
                </div>
                <BalanceLabel cents={g.myBalanceCents} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function CreateGroupForm() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const group = await api.createGroup(name);
      navigate(`/groups/${group.id}`);
    } catch (err) {
      setError(errorMessage(err));
      setSubmitting(false);
    }
  }

  return (
    <form className="card inline-form" onSubmit={onSubmit}>
      <label className="field grow">
        <span>New group</span>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Ski weekend, Flatmates" maxLength={60} required />
      </label>
      <button className="btn btn-primary" disabled={submitting || !name.trim()}>
        {submitting ? 'Creating…' : 'Create group'}
      </button>
      {error && <p className="error full-row">{error}</p>}
    </form>
  );
}
