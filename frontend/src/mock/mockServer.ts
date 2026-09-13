/**
 * In-browser stand-in for the FastAPI backend. Persists to localStorage (falls back to
 * memory) and behaves like the real API: token auth, membership checks, validation errors.
 *
 * Only `src/api.ts` should import this module.
 */
import { ApiError } from '../apiError';
import { computeNetBalances, simplifyDebts } from '../lib/balances';
import { formatCents, formatPercentHundredths } from '../lib/format';
import { allocateProportional, splitEvenly } from '../lib/split';
import type {
  AuthResponse,
  Balances,
  Expense,
  ExpenseSplit,
  Group,
  GroupSummary,
  LoginInput,
  NewExpense,
  NewSettlement,
  RegisterInput,
  Settlement,
  User,
} from '../types';

interface StoredUser extends User {
  password: string; // plaintext is acceptable only because this is a mock
}

interface StoredGroup {
  id: string;
  name: string;
  memberIds: string[];
  createdById: string;
  createdAt: string;
}

interface Db {
  users: StoredUser[];
  sessions: Record<string, string>; // token -> userId
  groups: StoredGroup[];
  expenses: Expense[];
  settlements: Settlement[];
}

const DB_KEY = 'spliteasy.mockdb.v1';
const LATENCY_MS = 200;

let memoryDb: Db | null = null;

function loadDb(): Db {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(DB_KEY);
  } catch {
    // localStorage unavailable (tests, privacy mode) — use memory
  }
  if (raw) return JSON.parse(raw) as Db;
  if (!memoryDb) saveDb(seedDb());
  return structuredClone(memoryDb!);
}

function saveDb(db: Db): void {
  memoryDb = structuredClone(db);
  try {
    localStorage.setItem(DB_KEY, JSON.stringify(db));
  } catch {
    // memory copy is enough
  }
}

async function handle<T>(fn: (db: Db) => T): Promise<T> {
  await new Promise((resolve) => setTimeout(resolve, LATENCY_MS));
  return fn(loadDb());
}

function newId(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function publicUser({ id, email, username }: StoredUser): User {
  return { id, email, username };
}

function requireUser(db: Db, token: string): StoredUser {
  const userId = db.sessions[token];
  const user = userId ? db.users.find((u) => u.id === userId) : undefined;
  if (!user) throw new ApiError(401, 'Your session has expired. Please sign in again.');
  return user;
}

function requireGroup(db: Db, groupId: string, userId: string): StoredGroup {
  const group = db.groups.find((g) => g.id === groupId);
  // Non-members get a 404 so group ids can't be probed.
  if (!group || !group.memberIds.includes(userId)) throw new ApiError(404, 'Group not found');
  return group;
}

function toGroup(db: Db, g: StoredGroup): Group {
  return {
    id: g.id,
    name: g.name,
    createdById: g.createdById,
    createdAt: g.createdAt,
    members: g.memberIds.map((id) => publicUser(db.users.find((u) => u.id === id)!)),
  };
}

function groupNet(db: Db, g: StoredGroup): Record<string, number> {
  return computeNetBalances(
    g.memberIds,
    db.expenses.filter((e) => e.groupId === g.id),
    db.settlements.filter((s) => s.groupId === g.id),
  );
}

function startSession(db: Db, user: StoredUser): AuthResponse {
  const token = `mock.${newId('tok')}.${Date.now()}`;
  db.sessions[token] = user.id;
  saveDb(db);
  return { token, user: publicUser(user) };
}

const byNewest = (a: { createdAt: string }, b: { createdAt: string }) =>
  b.createdAt.localeCompare(a.createdAt);

// ---- Auth ----

export function register(input: RegisterInput): Promise<AuthResponse> {
  return handle((db) => {
    const email = input.email.trim().toLowerCase();
    const username = input.username.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new ApiError(422, 'Enter a valid email address');
    if (!/^[A-Za-z0-9_]{3,20}$/.test(username)) {
      throw new ApiError(422, 'Username must be 3–20 letters, numbers or underscores');
    }
    if (input.password.length < 8) throw new ApiError(422, 'Password must be at least 8 characters');
    if (db.users.some((u) => u.email === email)) throw new ApiError(409, 'An account with that email already exists');
    if (db.users.some((u) => u.username.toLowerCase() === username.toLowerCase())) {
      throw new ApiError(409, 'That username is taken');
    }

    const user: StoredUser = { id: newId('usr'), email, username, password: input.password };
    db.users.push(user);
    return startSession(db, user);
  });
}

export function login(input: LoginInput): Promise<AuthResponse> {
  return handle((db) => {
    const identifier = input.identifier.trim().toLowerCase();
    const user = db.users.find(
      (u) => u.email === identifier || u.username.toLowerCase() === identifier,
    );
    if (!user || user.password !== input.password) throw new ApiError(401, 'Incorrect email/username or password');
    return startSession(db, user);
  });
}

export function logout(token: string): Promise<void> {
  return handle((db) => {
    delete db.sessions[token];
    saveDb(db);
  });
}

export function me(token: string): Promise<User> {
  return handle((db) => publicUser(requireUser(db, token)));
}

// ---- Groups ----

export function listGroups(token: string): Promise<GroupSummary[]> {
  return handle((db) => {
    const user = requireUser(db, token);
    return db.groups
      .filter((g) => g.memberIds.includes(user.id))
      .sort(byNewest)
      .map((g) => ({
        id: g.id,
        name: g.name,
        memberCount: g.memberIds.length,
        myBalanceCents: groupNet(db, g)[user.id] ?? 0,
      }));
  });
}

export function createGroup(token: string, name: string): Promise<Group> {
  return handle((db) => {
    const user = requireUser(db, token);
    const trimmed = name.trim();
    if (!trimmed) throw new ApiError(422, 'Group name is required');
    if (trimmed.length > 60) throw new ApiError(422, 'Group name must be 60 characters or fewer');

    const group: StoredGroup = {
      id: newId('grp'),
      name: trimmed,
      memberIds: [user.id],
      createdById: user.id,
      createdAt: new Date().toISOString(),
    };
    db.groups.push(group);
    saveDb(db);
    return toGroup(db, group);
  });
}

export function getGroup(token: string, groupId: string): Promise<Group> {
  return handle((db) => toGroup(db, requireGroup(db, groupId, requireUser(db, token).id)));
}

export function addMember(token: string, groupId: string, identifier: string): Promise<Group> {
  return handle((db) => {
    const group = requireGroup(db, groupId, requireUser(db, token).id);
    const needle = identifier.trim().toLowerCase();
    const invitee = db.users.find((u) => u.email === needle || u.username.toLowerCase() === needle);
    if (!invitee) throw new ApiError(404, 'No SplitEasy user with that email or username');
    if (group.memberIds.includes(invitee.id)) throw new ApiError(409, `${invitee.username} is already in this group`);

    group.memberIds.push(invitee.id);
    saveDb(db);
    return toGroup(db, group);
  });
}

// ---- Expenses ----

export function listExpenses(token: string, groupId: string): Promise<Expense[]> {
  return handle((db) => {
    requireGroup(db, groupId, requireUser(db, token).id);
    return db.expenses.filter((e) => e.groupId === groupId).sort(byNewest);
  });
}

export function createExpense(token: string, groupId: string, input: NewExpense): Promise<Expense> {
  return handle((db) => {
    const user = requireUser(db, token);
    const group = requireGroup(db, groupId, user.id);

    const description = input.description.trim();
    if (!description) throw new ApiError(422, 'Description is required');
    if (!Number.isInteger(input.amountCents) || input.amountCents <= 0) {
      throw new ApiError(422, 'Amount must be greater than zero');
    }
    if (!group.memberIds.includes(input.paidById)) throw new ApiError(422, 'The payer must be a group member');

    const seen = new Set<string>();
    for (const s of input.splits) {
      if (!group.memberIds.includes(s.userId)) throw new ApiError(422, 'Everyone in the split must be a group member');
      if (seen.has(s.userId)) throw new ApiError(422, 'Each member can appear in the split only once');
      if (!(s.value >= 0)) throw new ApiError(422, 'Split values cannot be negative');
      seen.add(s.userId);
    }
    const active = input.splits.filter((s) => s.value > 0);
    if (active.length === 0) throw new ApiError(422, 'Split the expense between at least one member');

    let splits: ExpenseSplit[];
    if (input.splitType === 'amount') {
      if (active.some((s) => !Number.isInteger(s.value))) throw new ApiError(422, 'Split amounts must be whole cents');
      const sum = active.reduce((acc, s) => acc + s.value, 0);
      if (sum !== input.amountCents) {
        throw new ApiError(422, `Splits add up to ${formatCents(sum)}, but the expense is ${formatCents(input.amountCents)}`);
      }
      splits = active.map((s) => ({ userId: s.userId, amountCents: s.value }));
    } else {
      const hundredths = active.map((s) => Math.round(s.value * 100));
      const sum = hundredths.reduce((a, b) => a + b, 0);
      if (sum !== 10000) throw new ApiError(422, `Percentages add up to ${formatPercentHundredths(sum)}%, not 100%`);
      const amounts = allocateProportional(input.amountCents, hundredths);
      splits = active.map((s, i) => ({ userId: s.userId, amountCents: amounts[i], percent: hundredths[i] / 100 }));
    }

    const expense: Expense = {
      id: newId('exp'),
      groupId,
      description,
      amountCents: input.amountCents,
      paidById: input.paidById,
      splitType: input.splitType,
      splits,
      createdById: user.id,
      createdAt: new Date().toISOString(),
    };
    db.expenses.push(expense);
    saveDb(db);
    return expense;
  });
}

// ---- Balances & settlements ----

export function getBalances(token: string, groupId: string): Promise<Balances> {
  return handle((db) => {
    const group = requireGroup(db, groupId, requireUser(db, token).id);
    const net = groupNet(db, group);
    return {
      net: group.memberIds.map((userId) => ({ userId, amountCents: net[userId] ?? 0 })),
      transfers: simplifyDebts(net),
    };
  });
}

export function listSettlements(token: string, groupId: string): Promise<Settlement[]> {
  return handle((db) => {
    requireGroup(db, groupId, requireUser(db, token).id);
    return db.settlements.filter((s) => s.groupId === groupId).sort(byNewest);
  });
}

export function createSettlement(token: string, groupId: string, input: NewSettlement): Promise<Settlement> {
  return handle((db) => {
    const user = requireUser(db, token);
    const group = requireGroup(db, groupId, user.id);
    if (!group.memberIds.includes(input.fromUserId) || !group.memberIds.includes(input.toUserId)) {
      throw new ApiError(422, 'Both people must be group members');
    }
    if (input.fromUserId === input.toUserId) throw new ApiError(422, 'Payer and recipient must be different people');
    if (!Number.isInteger(input.amountCents) || input.amountCents <= 0) {
      throw new ApiError(422, 'Amount must be greater than zero');
    }

    const settlement: Settlement = {
      id: newId('set'),
      groupId,
      fromUserId: input.fromUserId,
      toUserId: input.toUserId,
      amountCents: input.amountCents,
      createdById: user.id,
      createdAt: new Date().toISOString(),
    };
    db.settlements.push(settlement);
    saveDb(db);
    return settlement;
  });
}

// ---- Demo data ----

export function resetDemoData(): void {
  memoryDb = null;
  try {
    localStorage.removeItem(DB_KEY);
  } catch {
    // nothing stored
  }
}

function seedDb(): Db {
  const daysAgo = (n: number) => new Date(Date.now() - n * 86_400_000).toISOString();
  const user = (id: string, username: string): StoredUser => ({
    id,
    username,
    email: `${username}@example.com`,
    password: 'password123',
  });
  const even = (total: number, ids: string[]): ExpenseSplit[] =>
    splitEvenly(total, ids.length).map((amountCents, i) => ({ userId: ids[i], amountCents }));

  const trip = ['usr_alice', 'usr_bob', 'usr_carol'];
  const flat = ['usr_alice', 'usr_bob'];
  const dinner = allocateProportional(8450, [5000, 2500, 2500]);

  return {
    users: [user('usr_alice', 'alice'), user('usr_bob', 'bob'), user('usr_carol', 'carol'), user('usr_dave', 'dave')],
    sessions: {},
    groups: [
      { id: 'grp_lisbon', name: 'Lisbon Trip', memberIds: trip, createdById: 'usr_alice', createdAt: daysAgo(12) },
      { id: 'grp_flat', name: 'Apartment 4B', memberIds: flat, createdById: 'usr_bob', createdAt: daysAgo(30) },
    ],
    expenses: [
      {
        id: 'exp_airbnb', groupId: 'grp_lisbon', description: 'Airbnb (3 nights)', amountCents: 36000,
        paidById: 'usr_alice', splitType: 'amount', splits: even(36000, trip), createdById: 'usr_alice', createdAt: daysAgo(10),
      },
      {
        id: 'exp_dinner', groupId: 'grp_lisbon', description: 'Dinner at Time Out Market', amountCents: 8450,
        paidById: 'usr_bob', splitType: 'percent',
        splits: [
          { userId: 'usr_alice', amountCents: dinner[0], percent: 50 },
          { userId: 'usr_bob', amountCents: dinner[1], percent: 25 },
          { userId: 'usr_carol', amountCents: dinner[2], percent: 25 },
        ],
        createdById: 'usr_bob', createdAt: daysAgo(8),
      },
      {
        id: 'exp_internet', groupId: 'grp_flat', description: 'Internet — March', amountCents: 6000,
        paidById: 'usr_bob', splitType: 'amount', splits: even(6000, flat), createdById: 'usr_bob', createdAt: daysAgo(5),
      },
    ],
    settlements: [
      {
        id: 'set_carol', groupId: 'grp_lisbon', fromUserId: 'usr_carol', toUserId: 'usr_alice', amountCents: 5000,
        createdById: 'usr_carol', createdAt: daysAgo(6),
      },
    ],
  };
}
