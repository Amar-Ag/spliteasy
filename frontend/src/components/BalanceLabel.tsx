import { formatCents } from '../lib/format';

export function BalanceLabel({ cents }: { cents: number }) {
  if (cents > 0) return <span className="balance positive">you are owed {formatCents(cents)}</span>;
  if (cents < 0) return <span className="balance negative">you owe {formatCents(-cents)}</span>;
  return <span className="balance neutral">settled up</span>;
}
