import { describe, expect, it } from 'vitest';
import { parseDollars, parsePercent } from './format';
import { allocateProportional, splitEvenly } from './split';

describe('parsing', () => {
  it('parses dollar strings into cents', () => {
    expect(parseDollars('12')).toBe(1200);
    expect(parseDollars('$12.5')).toBe(1250);
    expect(parseDollars('0.07')).toBe(7);
    expect(parseDollars('12.345')).toBeNull();
    expect(parseDollars('-3')).toBeNull();
    expect(parseDollars('abc')).toBeNull();
  });

  it('parses percentages into hundredths and rejects > 100%', () => {
    expect(parsePercent('33.33')).toBe(3333);
    expect(parsePercent('100')).toBe(10000);
    expect(parsePercent('100.01')).toBeNull();
  });
});

// The backend allocates percentage splits the same way (app/money.py), so previews match what gets saved.
describe('allocation', () => {
  it('splits evenly with leftover cents going first', () => {
    expect(splitEvenly(1000, 3)).toEqual([334, 333, 333]);
  });

  it('allocates by weight and always sums to the total', () => {
    const parts = allocateProportional(8450, [5000, 2500, 2500]);
    expect(parts).toEqual([4225, 2113, 2112]);
    expect(parts.reduce((a, b) => a + b, 0)).toBe(8450);
  });

  it('never gives cents to zero weights', () => {
    expect(allocateProportional(101, [1, 0, 1])).toEqual([51, 0, 50]);
  });
});
