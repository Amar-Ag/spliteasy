/**
 * The single place the frontend talks to the backend (FastAPI, see backend/README.md).
 *
 * VITE_API_URL is the backend origin, defaulting to http://localhost:8000 for `npm run dev`.
 * Set it to an empty string when the backend serves this app itself, so calls stay same-origin.
 */
import { ApiError } from './apiError';
import type {
  AuthResponse,
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

const API_ORIGIN = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/+$/, '');
const API_URL = `${API_ORIGIN}/api`;
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

interface RequestOptions {
  method?: 'GET' | 'POST';
  body?: unknown;
  /** Send the stored token and sign the user out if the backend rejects it. */
  auth?: boolean;
}

async function request<T>(path: string, { method = 'GET', body, auth = true }: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  if (auth) {
    const token = tokenStore.get();
    if (!token) throw unauthorized('Please sign in');
    headers.Authorization = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, `Can't reach the SplitEasy server at ${API_URL}. Is the backend running?`);
  }

  if (res.status === 204) return undefined as T;

  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const message = errorDetail(data) ?? `Request failed (${res.status})`;
    throw auth && res.status === 401 ? unauthorized(message) : new ApiError(res.status, message);
  }
  return data as T;
}

function unauthorized(message: string): ApiError {
  tokenStore.clear();
  window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  return new ApiError(401, message);
}

function errorDetail(data: unknown): string | null {
  if (data && typeof data === 'object' && 'detail' in data) {
    const { detail } = data as { detail: unknown };
    if (typeof detail === 'string') return detail;
  }
  return null;
}

async function authenticate(path: string, body: RegisterInput | LoginInput): Promise<User> {
  const { token, user } = await request<AuthResponse>(path, { method: 'POST', body, auth: false });
  tokenStore.set(token);
  return user;
}

const groupPath = (groupId: string) => `/groups/${encodeURIComponent(groupId)}`;

export const api = {
  register: (input: RegisterInput): Promise<User> => authenticate('/auth/register', input),

  login: (input: LoginInput): Promise<User> => authenticate('/auth/login', input),

  async logout(): Promise<void> {
    const token = tokenStore.get();
    if (!token) return;
    // Revoke server-side, but never block signing out on it.
    await fetch(`${API_URL}/auth/logout`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } }).catch(
      () => undefined,
    );
    tokenStore.clear();
  },

  me: (): Promise<User> => request('/auth/me'),

  listGroups: (): Promise<GroupSummary[]> => request('/groups'),

  createGroup: (name: string): Promise<Group> => request('/groups', { method: 'POST', body: { name } }),

  getGroup: (groupId: string): Promise<Group> => request(groupPath(groupId)),

  addMember: (groupId: string, identifier: string): Promise<Group> =>
    request(`${groupPath(groupId)}/members`, { method: 'POST', body: { identifier } }),

  listExpenses: (groupId: string): Promise<Expense[]> => request(`${groupPath(groupId)}/expenses`),

  createExpense: (groupId: string, input: NewExpense): Promise<Expense> =>
    request(`${groupPath(groupId)}/expenses`, { method: 'POST', body: input }),

  getBalances: (groupId: string): Promise<Balances> => request(`${groupPath(groupId)}/balances`),

  listSettlements: (groupId: string): Promise<Settlement[]> => request(`${groupPath(groupId)}/settlements`),

  createSettlement: (groupId: string, input: NewSettlement): Promise<Settlement> =>
    request(`${groupPath(groupId)}/settlements`, { method: 'POST', body: input }),
};
