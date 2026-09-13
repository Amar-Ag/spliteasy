/**
 * The single place the frontend talks to the backend.
 *
 * Every call currently goes to an in-browser mock (src/mock/mockServer.ts). When the FastAPI
 * backend exists, replace each body with a fetch to the endpoint noted beside it — the rest of
 * the app only depends on these signatures.
 */
import { ApiError } from './apiError';
import * as server from './mock/mockServer';
import type {
  Balances,
  Expense,
  Group,
  GroupSummary,
  LoginInput,
  NewExpense,
  NewSettlement,
  RegisterInput,
  Settlement,
  User,
} from './types';

const TOKEN_KEY = 'spliteasy.token';

/** Fired when the backend rejects the stored token; AuthProvider signs the user out. */
export const UNAUTHORIZED_EVENT = 'spliteasy:unauthorized';

export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string): void {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      // session won't survive a reload
    }
  },
  clear(): void {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      // nothing stored
    }
  },
};

async function authed<T>(request: (token: string) => Promise<T>): Promise<T> {
  try {
    const token = tokenStore.get();
    if (!token) throw new ApiError(401, 'Please sign in');
    return await request(token);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      tokenStore.clear();
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    throw err;
  }
}

export const api = {
  // POST /auth/register
  async register(input: RegisterInput): Promise<User> {
    const { token, user } = await server.register(input);
    tokenStore.set(token);
    return user;
  },

  // POST /auth/login
  async login(input: LoginInput): Promise<User> {
    const { token, user } = await server.login(input);
    tokenStore.set(token);
    return user;
  },

  // POST /auth/logout
  async logout(): Promise<void> {
    const token = tokenStore.get();
    tokenStore.clear();
    if (token) await server.logout(token).catch(() => undefined);
  },

  // GET /auth/me
  me: (): Promise<User> => authed((t) => server.me(t)),

  // GET /groups
  listGroups: (): Promise<GroupSummary[]> => authed((t) => server.listGroups(t)),

  // POST /groups
  createGroup: (name: string): Promise<Group> => authed((t) => server.createGroup(t, name)),

  // GET /groups/{groupId}
  getGroup: (groupId: string): Promise<Group> => authed((t) => server.getGroup(t, groupId)),

  // POST /groups/{groupId}/members
  addMember: (groupId: string, identifier: string): Promise<Group> =>
    authed((t) => server.addMember(t, groupId, identifier)),

  // GET /groups/{groupId}/expenses
  listExpenses: (groupId: string): Promise<Expense[]> => authed((t) => server.listExpenses(t, groupId)),

  // POST /groups/{groupId}/expenses
  createExpense: (groupId: string, input: NewExpense): Promise<Expense> =>
    authed((t) => server.createExpense(t, groupId, input)),

  // GET /groups/{groupId}/balances
  getBalances: (groupId: string): Promise<Balances> => authed((t) => server.getBalances(t, groupId)),

  // GET /groups/{groupId}/settlements
  listSettlements: (groupId: string): Promise<Settlement[]> => authed((t) => server.listSettlements(t, groupId)),

  // POST /groups/{groupId}/settlements
  createSettlement: (groupId: string, input: NewSettlement): Promise<Settlement> =>
    authed((t) => server.createSettlement(t, groupId, input)),

  /** Mock only: wipes local data and restores the demo accounts. Remove with the mock. */
  resetDemoData(): void {
    tokenStore.clear();
    server.resetDemoData();
  },
};
