import { beforeEach, describe, expect, it } from 'vitest';
import * as server from './mockServer';

describe('mock server', () => {
  beforeEach(() => server.resetDemoData());

  it('runs the full flow: register, group, invite, expense, settle', async () => {
    const { token } = await server.register({ email: 'zoe@example.com', username: 'zoe', password: 'longenough' });

    const group = await server.createGroup(token, 'Road trip');
    const withBob = await server.addMember(token, group.id, 'bob');
    const bobId = withBob.members.find((m) => m.username === 'bob')!.id;
    const zoeId = withBob.members.find((m) => m.username === 'zoe')!.id;

    await server.createExpense(token, group.id, {
      description: 'Gas',
      amountCents: 9000,
      paidById: zoeId,
      splitType: 'percent',
      splits: [
        { userId: zoeId, value: 40 },
        { userId: bobId, value: 60 },
      ],
    });

    let balances = await server.getBalances(token, group.id);
    expect(balances.transfers).toEqual([{ fromUserId: bobId, toUserId: zoeId, amountCents: 5400 }]);

    await server.createSettlement(token, group.id, { fromUserId: bobId, toUserId: zoeId, amountCents: 5400 });
    balances = await server.getBalances(token, group.id);
    expect(balances.transfers).toEqual([]);
  });

  it('rejects splits that do not add up', async () => {
    const { token, user } = await server.login({ identifier: 'alice', password: 'password123' });
    await expect(
      server.createExpense(token, 'grp_lisbon', {
        description: 'Taxi',
        amountCents: 2000,
        paidById: user.id,
        splitType: 'amount',
        splits: [{ userId: user.id, value: 1500 }],
      }),
    ).rejects.toMatchObject({ status: 422 });
  });

  it('hides groups from non-members', async () => {
    const { token } = await server.login({ identifier: 'dave', password: 'password123' });
    await expect(server.getGroup(token, 'grp_lisbon')).rejects.toMatchObject({ status: 404 });
  });

  it('rejects bad credentials and bad tokens', async () => {
    await expect(server.login({ identifier: 'alice', password: 'nope' })).rejects.toMatchObject({ status: 401 });
    await expect(server.listGroups('bogus')).rejects.toMatchObject({ status: 401 });
  });
});
