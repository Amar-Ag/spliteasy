import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api';
import { useAuth } from '../auth/AuthContext';
import { BalanceLabel } from '../components/BalanceLabel';
import { BalancesTab } from '../components/BalancesTab';
import { ExpensesTab } from '../components/ExpensesTab';
import { MembersTab } from '../components/MembersTab';
import type { People } from '../components/people';
import { useResource } from '../lib/useResource';

type Tab = 'expenses' | 'balances' | 'members';
const TABS: { id: Tab; label: string }[] = [
  { id: 'expenses', label: 'Expenses' },
  { id: 'balances', label: 'Balances' },
  { id: 'members', label: 'Members' },
];

export function GroupPage() {
  const { groupId = '' } = useParams();
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>('expenses');

  const { data, error, reload } = useResource(async () => {
    const [group, expenses, settlements, balances] = await Promise.all([
      api.getGroup(groupId),
      api.listExpenses(groupId),
      api.listSettlements(groupId),
      api.getBalances(groupId),
    ]);
    return { group, expenses, settlements, balances };
  }, [groupId]);

  const backLink = (
    <Link to="/" className="back-link">
      ← All groups
    </Link>
  );

  if (!data || data.group.id !== groupId) {
    return (
      <>
        {backLink}
        {error ? <p className="error">{error}</p> : <p className="muted">Loading group…</p>}
      </>
    );
  }

  const { group, expenses, settlements, balances } = data;
  const currentUserId = user!.id;
  const username = (id: string) => group.members.find((m) => m.id === id)?.username ?? 'Someone';
  const people: People = {
    currentUserId,
    subject: (id) => (id === currentUserId ? 'You' : username(id)),
    object: (id) => (id === currentUserId ? 'you' : username(id)),
  };
  const myNet = balances.net.find((n) => n.userId === currentUserId)?.amountCents ?? 0;

  return (
    <>
      {backLink}
      <div className="page-header">
        <div>
          <h1>{group.name}</h1>
          <p className="muted">{group.members.map((m) => people.subject(m.id)).join(', ')}</p>
        </div>
        <div className="my-balance">
          <span className="muted small">Your balance</span>
          <BalanceLabel cents={myNet} />
        </div>
      </div>

      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? 'tab active' : 'tab'} onClick={() => setTab(t.id)}>
            {t.label}
            {t.id === 'balances' && balances.transfers.length > 0 && <span className="badge">{balances.transfers.length}</span>}
          </button>
        ))}
      </nav>

      {error && <p className="error">{error}</p>}

      {tab === 'expenses' && <ExpensesTab group={group} expenses={expenses} people={people} onChanged={reload} onInvite={() => setTab('members')} />}
      {tab === 'balances' && <BalancesTab group={group} balances={balances} settlements={settlements} people={people} onChanged={reload} />}
      {tab === 'members' && <MembersTab group={group} people={people} onChanged={reload} />}
    </>
  );
}
