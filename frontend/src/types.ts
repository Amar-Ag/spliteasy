// Shapes exchanged with the backend. Money is always integer cents.

export interface User {
  id: string;
  email: string;
  username: string;
}

export interface RegisterInput {
  email: string;
  username: string;
  password: string;
}

export interface LoginInput {
  /** Email or username. */
  identifier: string;
  password: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface Group {
  id: string;
  name: string;
  members: User[];
  createdById: string;
  createdAt: string;
}

export interface GroupSummary {
  id: string;
  name: string;
  memberCount: number;
  /** Positive: the current user is owed money. Negative: they owe money. */
  myBalanceCents: number;
}

export type SplitType = 'amount' | 'percent';

export interface ExpenseSplit {
  userId: string;
  amountCents: number;
  /** Present when the expense was split by percentage. */
  percent?: number;
}

export interface Expense {
  id: string;
  groupId: string;
  description: string;
  amountCents: number;
  paidById: string;
  splitType: SplitType;
  splits: ExpenseSplit[];
  createdById: string;
  createdAt: string;
}

export interface NewExpense {
  description: string;
  amountCents: number;
  paidById: string;
  splitType: SplitType;
  /** `value` is cents when splitType is 'amount', a percentage (0–100) when 'percent'. */
  splits: { userId: string; value: number }[];
}

export interface Settlement {
  id: string;
  groupId: string;
  fromUserId: string;
  toUserId: string;
  amountCents: number;
  createdById: string;
  createdAt: string;
}

export interface NewSettlement {
  fromUserId: string;
  toUserId: string;
  amountCents: number;
}

export interface Transfer {
  fromUserId: string;
  toUserId: string;
  amountCents: number;
}

export interface Balances {
  net: { userId: string; amountCents: number }[];
  /** Minimal set of payments that would settle the group. */
  transfers: Transfer[];
}
