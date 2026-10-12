import { screen } from '@testing-library/react';

import type { Order } from '@/api/types';

import { makeMe, mockApi, renderApp } from './utils';

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

function order(extra: Partial<Order> = {}): Order {
  return {
    id: 42,
    order_number: 'A-007',
    canteen_id: 1,
    canteen_name: 'Главная столовая',
    service_date: '2026-10-12',
    channel: 'mobile_app',
    status: 'pending_payment',
    pickup_slot: { id: 7, slot_date: '2026-10-12', starts_at: '12:00:00', ends_at: '12:10:00' },
    subtotal: '3000.00',
    discount_total: '300.00',
    total: '2700.00',
    qr_token: '00000000-0000-0000-0000-000000000000',
    pickup_shelf: null,
    allergy_warning_ack: false,
    created_at: '2026-10-12T04:00:00Z',
    paid_at: null,
    ready_at: null,
    picked_up_at: null,
    items: [
      {
        id: 1,
        menu_item_id: 1,
        dish_id: 1,
        name_ru: 'Плов',
        name_kk: 'Палау',
        quantity: 2,
        unit_price: '1500.00',
        discount_amount: '300.00',
        line_total: '2700.00',
        promotion_id: 3,
      },
    ],
    payment_id: 1,
    payment_url: null,
    can_cancel: true,
    cancel_until: null,
    no_show_warning: false,
    ...extra,
  };
}

describe('orders', () => {
  it('shows the order number, slot, status and cancel', async () => {
    mockApi({ '/me': makeMe('student'), '/orders/42': order() });
    renderApp('/orders/42', makeMe('student'));
    expect(await screen.findByText('A-007')).toBeInTheDocument();
    expect(screen.getByText('Ждёт оплаты')).toBeInTheDocument();
    expect(screen.getByText(/12:00–12:10/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Отменить заказ' })).toBeInTheDocument();
  });

  it('lists my orders with an empty state', async () => {
    mockApi({ '/me': makeMe('student'), '/orders': { items: [], total: 0 } });
    renderApp('/orders', makeMe('student'));
    expect(await screen.findByText('У вас пока нет заказов.')).toBeInTheDocument();
  });

  it('lists orders', async () => {
    mockApi({
      '/me': makeMe('student'),
      '/orders': { items: [order({ status: 'ready', can_cancel: false })], total: 1 },
    });
    renderApp('/orders', makeMe('student'));
    expect(await screen.findByText('A-007')).toBeInTheDocument();
    expect(screen.getByText('Готов')).toBeInTheDocument();
  });
});
