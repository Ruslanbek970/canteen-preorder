import type { MenuItem } from '@/api/types';

export function menuItem(overrides: Partial<MenuItem> = {}): MenuItem {
  return {
    id: 1,
    dish_id: 1,
    name_ru: 'Плов',
    name_kk: 'Палау',
    description: null,
    category_id: 2,
    category_name: 'Вторые блюда',
    category_sort: 2,
    price: '1500.00',
    price_now: '1500',
    discount_percent: null,
    promotion_id: null,
    available_portions: 10,
    portion_grams: 350,
    calories: 650,
    protein_g: '22.0',
    fat_g: '26.0',
    carbs_g: '80.0',
    is_halal: true,
    is_vegetarian: false,
    photo_url: null,
    allergens: [],
    rating: null,
    rating_count: 0,
    unsafe_for_me: false,
    warning_for_me: false,
    my_allergens: [],
    ...overrides,
  };
}
