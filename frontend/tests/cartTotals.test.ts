import { lineFromItem } from '@/features/cart/store';
import { cartTotals, lineDiscount } from '@/features/cart/totals';

import { menuItem } from './fixtures';

describe('cart totals (same rule as the server)', () => {
  it('sums lines without discounts', () => {
    const lines = [
      lineFromItem(menuItem({ id: 1, price: '1500.00' }), 2),
      lineFromItem(menuItem({ id: 2, price: '150.00' }), 3),
    ];
    expect(cartTotals(lines)).toEqual({ subtotal: 3450, discount: 0, total: 3450 });
  });

  it('applies the biggest of item and slot discounts per line', () => {
    const lines = [
      lineFromItem(menuItem({ id: 1, price: '1500.00', discount_percent: 15 }), 2),
      lineFromItem(menuItem({ id: 2, price: '150.00' }), 3),
    ];
    // Плов 15% (item beats slot 10%): 450; Чай 10% from the slot: 45.
    expect(cartTotals(lines, 10)).toEqual({ subtotal: 3450, discount: 495, total: 2955 });
  });

  it('rounds per unit to whole tenge', () => {
    // 1250 * 0.85 = 1062.5 -> 1063 each, so the discount is 187 per unit.
    expect(lineDiscount(1250, 2, 15)).toBe(374);
    expect(lineDiscount(1250, 2, null)).toBe(0);
  });
});
