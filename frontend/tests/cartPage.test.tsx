import { act, fireEvent, screen, waitFor } from '@testing-library/react';

import { useCartStore } from '@/features/cart/store';

import { menuItem } from './fixtures';
import { makeMe, mockApi, renderApp } from './utils';

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
  act(() => useCartStore.getState().clear());
});

const slots = {
  canteen_id: 1,
  date: '2026-10-12',
  slots: [
    {
      id: 7,
      slot_date: '2026-10-12',
      starts_at: '12:00:00',
      ends_at: '12:10:00',
      capacity: 30,
      booked_count: 5,
      free: 25,
      is_closed: false,
      discount_percent: 10,
      promotion_id: 3,
    },
  ],
  hidden: { by_schedule: 4, too_late: 0, full: 0, closed: 0 },
  total: 5,
  cutoff_minutes: 15,
  schedule_applied: true,
};

describe('cart page', () => {
  it('explains hidden slots, applies the slot discount and places the order', async () => {
    useCartStore.getState().add(menuItem({ id: 1, price: '1500.00' }), 1, '2026-10-12');
    const fetchMock = mockApi({
      '/me': makeMe('student'),
      '/canteens/1/slots': slots,
      '/orders': (_path: string, init?: RequestInit) =>
        init?.method === 'POST'
          ? { id: 42, order_number: 'A-001', items: [] }
          : { items: [], total: 0 },
    });
    const router = renderApp('/cart', makeMe('student'));

    expect(await screen.findByText(/у вашей группы пары/)).toBeInTheDocument();
    expect(screen.getByTestId('cart-total')).toHaveTextContent('1 500');

    fireEvent.click(screen.getByRole('button', { name: /12:00/ }));
    expect(screen.getByTestId('cart-total')).toHaveTextContent('1 350');

    fireEvent.click(screen.getByRole('button', { name: /Заказать за/ }));
    await waitFor(() => expect(router.state.location.pathname).toBe('/orders/42'));
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      canteen_id: 1,
      pickup_slot_id: 7,
      items: [{ menu_item_id: 1, quantity: 1 }],
      allergy_warning_ack: false,
    });
    expect(useCartStore.getState().lines).toEqual([]);
  });

  it('requires the allergy confirmation for warned dishes', async () => {
    useCartStore
      .getState()
      .add(menuItem({ id: 2, name_ru: 'Латте', warning_for_me: true }), 1, '2026-10-12');
    useCartStore.getState().setSlot(7);
    mockApi({ '/me': makeMe('student'), '/canteens/1/slots': slots });
    renderApp('/cart', makeMe('student'));
    const place = await screen.findByRole('button', { name: /Заказать за/ });
    expect(place).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox'));
    expect(place).toBeEnabled();
  });

  it('shows an empty state', async () => {
    mockApi({ '/me': makeMe('student') });
    renderApp('/cart', makeMe('student'));
    expect(await screen.findByText('Корзина пуста.')).toBeInTheDocument();
  });
});

describe('menu → cart', () => {
  it('adds a dish and blocks unsafe ones', async () => {
    mockApi({
      '/me': makeMe('student'),
      '/canteens/1/menu': {
        canteen_id: 1,
        date: '2026-10-12',
        available_dates: ['2026-10-12'],
        items: [
          menuItem({ id: 1, name_ru: 'Плов' }),
          menuItem({ id: 2, dish_id: 2, name_ru: 'Медовик', unsafe_for_me: true }),
        ],
      },
      '/canteens': [{ id: 1, name: 'Главная', slug: 'main', is_active: true }],
    });
    renderApp('/menu', makeMe('student'));
    expect(await screen.findByRole('button', { name: 'В корзину: Медовик' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'В корзину: Плов' }));
    expect(useCartStore.getState().lines).toHaveLength(1);
    expect(await screen.findByText(/Корзина · 1 шт\./)).toBeInTheDocument();
  });
});
