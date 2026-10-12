import type { MenuItem } from '@/api/types';

export interface MenuFilters {
  categoryId: number | null;
  safeForMe: boolean;
  halal: boolean;
  vegetarian: boolean;
}

export const DEFAULT_FILTERS: MenuFilters = {
  categoryId: null,
  safeForMe: false,
  halal: false,
  vegetarian: false,
};

/** Client-side menu filters (SPEC 7.2): category, «без моих аллергенов», halal, vegetarian. */
export function filterMenu(items: MenuItem[], f: MenuFilters): MenuItem[] {
  return items.filter(
    (i) =>
      (f.categoryId === null || i.category_id === f.categoryId) &&
      (!f.safeForMe || i.my_allergens.length === 0) &&
      (!f.halal || i.is_halal) &&
      (!f.vegetarian || i.is_vegetarian),
  );
}

export function categoriesOf(items: MenuItem[]): { id: number; name: string }[] {
  const seen = new Map<number, { id: number; name: string; sort: number }>();
  for (const i of items) {
    if (!seen.has(i.category_id)) {
      seen.set(i.category_id, { id: i.category_id, name: i.category_name, sort: i.category_sort });
    }
  }
  return [...seen.values()].sort((a, b) => a.sort - b.sort).map(({ id, name }) => ({ id, name }));
}
