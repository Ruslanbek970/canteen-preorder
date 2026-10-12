import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

import type { MenuItem } from '@/api/types';

export const MAX_LINES = 10;
export const MAX_QUANTITY = 10;

export interface CartLine {
  menuItemId: number;
  dishId: number;
  nameRu: string;
  nameKk: string | null;
  price: string;
  discountPercent: number | null;
  quantity: number;
  available: number;
  warning: boolean;
}

export interface CartState {
  canteenId: number | null;
  date: string | null;
  slotId: number | null;
  lines: CartLine[];
  add: (item: MenuItem, canteenId: number, date: string) => void;
  setQuantity: (menuItemId: number, quantity: number) => void;
  setSlot: (slotId: number | null) => void;
  replace: (canteenId: number, date: string, lines: CartLine[]) => void;
  clear: () => void;
}

export function lineFromItem(item: MenuItem, quantity = 1): CartLine {
  return {
    menuItemId: item.id,
    dishId: item.dish_id,
    nameRu: item.name_ru,
    nameKk: item.name_kk,
    price: item.price,
    discountPercent: item.discount_percent,
    quantity,
    available: item.available_portions,
    warning: item.warning_for_me,
  };
}

const EMPTY = { canteenId: null, date: null, slotId: null, lines: [] };

export const useCartStore = create<CartState>()(
  persist(
    (set) => ({
      ...EMPTY,
      add: (item, canteenId, date) =>
        set((s) => {
          // One cart = one canteen and one day; switching starts a new cart.
          const fresh = s.canteenId !== canteenId || s.date !== date;
          const lines = fresh ? [] : s.lines;
          const existing = lines.find((l) => l.menuItemId === item.id);
          if (existing) {
            const quantity = Math.min(existing.quantity + 1, MAX_QUANTITY, item.available_portions);
            return {
              lines: lines.map((l) =>
                l.menuItemId === item.id ? { ...lineFromItem(item), quantity } : l,
              ),
            };
          }
          if (lines.length >= MAX_LINES) return {};
          return {
            canteenId,
            date,
            slotId: fresh ? null : s.slotId,
            lines: [...lines, lineFromItem(item)],
          };
        }),
      setQuantity: (menuItemId, quantity) =>
        set((s) => ({
          lines:
            quantity <= 0
              ? s.lines.filter((l) => l.menuItemId !== menuItemId)
              : s.lines.map((l) =>
                  l.menuItemId === menuItemId
                    ? { ...l, quantity: Math.min(quantity, MAX_QUANTITY) }
                    : l,
                ),
        })),
      setSlot: (slotId) => set({ slotId }),
      replace: (canteenId, date, lines) => set({ canteenId, date, slotId: null, lines }),
      clear: () => set(EMPTY),
    }),
    { name: 'canteen-cart', storage: createJSONStorage(() => localStorage) },
  ),
);

export function cartCount(lines: CartLine[]): number {
  return lines.reduce((sum, l) => sum + l.quantity, 0);
}
