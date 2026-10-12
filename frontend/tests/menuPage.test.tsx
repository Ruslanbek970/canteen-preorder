import { screen } from '@testing-library/react';

import { makeMe, mockApi, renderApp } from './utils';
import { menuItem } from './fixtures';

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

const canteen = {
  id: 1,
  name: 'Главная столовая',
  building_id: 1,
  opens_at: '09:00:00',
  closes_at: '17:00:00',
  slug: 'main',
  is_active: true,
  order_cutoff_minutes: 15,
};

describe('menu page', () => {
  it('marks unsafe dishes and sold out ones', async () => {
    mockApi({
      '/me': makeMe('student'),
      '/canteens/1/menu': {
        canteen_id: 1,
        date: '2026-10-12',
        available_dates: ['2026-10-12'],
        items: [
          menuItem({
            id: 1,
            name_ru: 'Медовик',
            unsafe_for_me: true,
            my_allergens: ['nuts'],
            allergens: [{ id: 4, code: 'nuts', name_ru: 'Орехи', name_kk: 'Жаңғақ' }],
          }),
          menuItem({ id: 2, name_ru: 'Плов', available_portions: 0 }),
        ],
      },
      '/canteens': [canteen],
    });
    renderApp('/menu', makeMe('student'));
    expect(await screen.findByText('Медовик')).toBeInTheDocument();
    expect(screen.getByText(/Опасно для вас/)).toBeInTheDocument();
    expect(screen.getByText('Закончилось')).toBeInTheDocument();
  });

  it('public canteen page works without signing in', async () => {
    mockApi({
      '/canteens/by-slug/main': canteen,
      '/canteens/1/menu': {
        canteen_id: 1,
        date: '2026-10-12',
        available_dates: ['2026-10-12'],
        items: [menuItem()],
      },
    });
    renderApp('/c/main');
    expect(await screen.findByText('Плов')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Войти, чтобы заказать' })).toBeInTheDocument();
  });
});
