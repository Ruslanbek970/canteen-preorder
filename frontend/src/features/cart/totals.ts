import type { CartLine } from './store';

export interface Totals {
  subtotal: number;
  discount: number;
  total: number;
}

const round = (value: number) => Math.round(value);

/** Same rule as the server (pricing.py): one discount per line, the biggest one,
 *  rounded per unit to whole tenge. The server total is the one that counts. */
export function lineDiscount(price: number, quantity: number, percent: number | null): number {
  if (!percent) return 0;
  return (round(price) - round((price * (100 - percent)) / 100)) * quantity;
}

export function cartTotals(lines: CartLine[], slotPercent: number | null = null): Totals {
  let subtotal = 0;
  let discount = 0;
  for (const line of lines) {
    const price = Number(line.price);
    const percent = Math.max(line.discountPercent ?? 0, slotPercent ?? 0) || null;
    subtotal += price * line.quantity;
    discount += lineDiscount(price, line.quantity, percent);
  }
  return { subtotal, discount, total: subtotal - discount };
}
