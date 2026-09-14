import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, tokenStore, UNAUTHORIZED_EVENT } from './api';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('api client', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let storage: Map<string, string>;

  beforeEach(() => {
    storage = new Map();
    vi.stubGlobal('localStorage', {
      getItem: (k: string) => storage.get(k) ?? null,
      setItem: (k: string, v: string) => storage.set(k, v),
      removeItem: (k: string) => storage.delete(k),
    });
    vi.stubGlobal('window', new EventTarget());
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => vi.unstubAllGlobals());

  it('logs in against the backend and stores the token', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { token: 'jwt-123', user: { id: 'u1', email: 'a@x.com', username: 'alice' } }));

    const user = await api.login({ identifier: 'alice', password: 'password123' });

    expect(user.username).toBe('alice');
    expect(tokenStore.get()).toBe('jwt-123');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('http://localhost:8000/auth/login');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ identifier: 'alice', password: 'password123' });
    expect(init.headers.Authorization).toBeUndefined();
  });

  it('sends the bearer token on authenticated calls', async () => {
    tokenStore.set('jwt-123');
    fetchMock.mockResolvedValue(jsonResponse(200, []));

    await api.listExpenses('grp 1');

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('http://localhost:8000/groups/grp%201/expenses');
    expect(init.headers.Authorization).toBe('Bearer jwt-123');
  });

  it('surfaces the backend detail message as an ApiError', async () => {
    tokenStore.set('jwt-123');
    fetchMock.mockResolvedValue(jsonResponse(422, { detail: 'Group name is required' }));

    await expect(api.createGroup('')).rejects.toMatchObject({ status: 422, message: 'Group name is required' });
  });

  it('clears the token and signals sign-out when the backend returns 401', async () => {
    tokenStore.set('expired');
    fetchMock.mockResolvedValue(jsonResponse(401, { detail: 'Your session has expired. Please sign in again.' }));
    const onUnauthorized = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);

    await expect(api.me()).rejects.toMatchObject({ status: 401 });

    expect(tokenStore.get()).toBeNull();
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it('does not sign anyone out when login credentials are wrong', async () => {
    fetchMock.mockResolvedValue(jsonResponse(401, { detail: 'Incorrect email/username or password' }));
    const onUnauthorized = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);

    await expect(api.login({ identifier: 'alice', password: 'nope' })).rejects.toMatchObject({
      status: 401,
      message: 'Incorrect email/username or password',
    });
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('explains when the backend is unreachable', async () => {
    tokenStore.set('jwt-123');
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(api.listGroups()).rejects.toMatchObject({ status: 0, message: expect.stringContaining('backend running') });
  });

  it('revokes the token on logout', async () => {
    tokenStore.set('jwt-123');
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await api.logout();

    expect(fetchMock.mock.calls[0][0]).toBe('http://localhost:8000/auth/logout');
    expect(tokenStore.get()).toBeNull();
  });
});
