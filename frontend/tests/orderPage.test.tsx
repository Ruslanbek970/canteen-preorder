import { act, fireEvent, screen, waitFor } from '@testing-library/react';

import type { Order } from '@/api/types';

import { FakeWebSocket } from './setup';
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
    pay_until: null,
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

describe('payment', () => {
  it('pending order links to the mock payment page', async () => {
    mockApi({
      '/me': makeMe('student'),
      '/orders/42': order({ payment_url: '/pay/mock/1', pay_until: '2026-10-12T04:10:00Z' }),
    });
    renderApp('/orders/42', makeMe('student'));
    const link = await screen.findByRole('link', { name: /Оплатить 2\s700/ });
    expect(link).toHaveAttribute('href', '/pay/mock/1');
    expect(screen.getByText(/Оплатите до 09:10/)).toBeInTheDocument();
  });

  it('paid order shows the QR code instead of the pay button', async () => {
    mockApi({ '/me': makeMe('student'), '/orders/42': order({ status: 'paid' }) });
    renderApp('/orders/42', makeMe('student'));
    expect(await screen.findByRole('img', { name: 'QR-код заказа' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Оплатить/ })).not.toBeInTheDocument();
  });

  it('mock page confirms and returns to the order', async () => {
    const fetchMock = mockApi({
      '/me': makeMe('student'),
      '/payments/mock/1/confirm': { id: 1, order_id: 42, status: 'succeeded' },
      '/payments/1': {
        id: 1,
        order_id: 42,
        order_number: 'A-007',
        canteen_name: 'Главная столовая',
        method: 'kaspi_qr',
        amount: '2700.00',
        status: 'pending',
        url: '/pay/mock/1',
        fiscal_receipt_number: null,
      },
      '/orders/42': order({ status: 'paid' }),
    });
    const router = renderApp('/pay/mock/1', makeMe('student'));
    fireEvent.click(await screen.findByRole('button', { name: 'Оплатить' }));
    await waitFor(() => expect(router.state.location.pathname).toBe('/orders/42'));
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/mock/1/confirm'))).toBe(
      true,
    );
  });

  it('a status event over /ws/me refetches the order', async () => {
    let status = 'pending_payment';
    mockApi({ '/me': makeMe('student'), '/orders/42': () => order({ status } as Partial<Order>) });
    renderApp('/orders/42', makeMe('student'));
    expect(await screen.findByText('Ждёт оплаты')).toBeInTheDocument();
    const socket = FakeWebSocket.instances.at(-1);
    expect(socket?.url).toContain('/ws/me?token=token');
    status = 'cooking';
    act(() => socket?.onmessage?.({ data: JSON.stringify({ type: 'order.status_changed' }) }));
    expect(await screen.findByText('Готовится')).toBeInTheDocument();
  });
});
