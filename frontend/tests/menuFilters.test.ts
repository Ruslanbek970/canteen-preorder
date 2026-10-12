import type { MenuItem } from '@/api/types';
import { DEFAULT_FILTERS, categoriesOf, filterMenu } from '@/features/menu/filters';

import { menuItem } from './fixtures';

const items = [
  menuItem({ id: 1, name_ru: 'Плов' }),
  menuItem({
    id: 2,
    name_ru: 'Салат',
    category_id: 3,
    category_name: 'Салаты',
    category_sort: 3,
    is_vegetarian: true,
  }),
  menuItem({
    id: 3,
    name_ru: 'Медовик',
    category_id: 4,
    category_name: 'Десерты',
    category_sort: 4,
    my_allergens: ['nuts'],
    unsafe_for_me: true,
    is_halal: false,
  }),
  menuItem({
    id: 4,
    name_ru: 'Чай',
    category_id: 1,
    category_name: 'Напитки',
    category_sort: 1,
    my_allergens: ['milk'],
    warning_for_me: true,
  }),
];

const names = (list: MenuItem[]) => list.map((i) => i.name_ru);

describe('menu filters', () => {
  it('shows everything by default', () => {
    expect(names(filterMenu(items, DEFAULT_FILTERS))).toEqual(['Плов', 'Салат', 'Медовик', 'Чай']);
  });

  it('filters by category', () => {
    expect(names(filterMenu(items, { ...DEFAULT_FILTERS, categoryId: 3 }))).toEqual(['Салат']);
  });

  it('hides dishes with my allergens', () => {
    expect(names(filterMenu(items, { ...DEFAULT_FILTERS, safeForMe: true }))).toEqual([
      'Плов',
      'Салат',
    ]);
  });

  it('combines halal and vegetarian', () => {
    expect(names(filterMenu(items, { ...DEFAULT_FILTERS, halal: true }))).toEqual([
      'Плов',
      'Салат',
      'Чай',
    ]);
    expect(names(filterMenu(items, { ...DEFAULT_FILTERS, halal: true, vegetarian: true }))).toEqual(
      ['Салат'],
    );
  });

  it('lists categories in menu order', () => {
    expect(categoriesOf(items).map((c) => c.name)).toEqual([
      'Напитки',
      'Вторые блюда',
      'Салаты',
      'Десерты',
    ]);
  });
});
