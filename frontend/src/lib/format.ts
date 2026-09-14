const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const date = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

export function formatCents(cents: number): string {
  return currency.format(cents / 100);
}

export function formatDate(iso: string): string {
  return date.format(new Date(iso));
}

/** Parses "12", "12.5", "$12.50" into cents. Returns null for anything else. */
export function parseDollars(input: string): number | null {
  return parseHundredths(input.trim().replace(/^\$/, ''));
}

/** Parses "33.33" into hundredths of a percent (3333). Returns null if invalid or over 100%. */
export function parsePercent(input: string): number | null {
  const value = parseHundredths(input.trim().replace(/%$/, ''));
  return value !== null && value <= 10000 ? value : null;
}

export function centsToInput(cents: number): string {
  return (cents / 100).toFixed(2);
}

export function formatPercentHundredths(value: number): string {
  return String(Number((value / 100).toFixed(2)));
}

function parseHundredths(s: string): number | null {
  if (!/^\d+(\.\d{0,2})?$/.test(s)) return null;
  const [whole, frac = ''] = s.split('.');
  return Number(whole) * 100 + Number(frac.padEnd(2, '0'));
}
