/**
 * Splits an integer `total` into integer parts proportional to `weights`.
 * Rounding leftovers go to the parts with the largest fractional remainder
 * (earlier index wins ties), so the parts always sum exactly to `total`.
 */
export function allocateProportional(total: number, weights: number[]): number[] {
  const weightSum = weights.reduce((a, b) => a + b, 0);
  if (weightSum <= 0) return weights.map(() => 0);

  const raw = weights.map((w) => (total * w) / weightSum);
  const parts = raw.map((r) => Math.floor(r));
  let remainder = total - parts.reduce((a, b) => a + b, 0);

  const order = raw
    .map((r, i) => ({ i, frac: r - Math.floor(r) }))
    .sort((a, b) => b.frac - a.frac || a.i - b.i);
  for (let k = 0; remainder > 0; k++, remainder--) {
    parts[order[k % order.length].i] += 1;
  }
  return parts;
}

export function splitEvenly(total: number, count: number): number[] {
  return allocateProportional(total, Array.from({ length: count }, () => 1));
}
