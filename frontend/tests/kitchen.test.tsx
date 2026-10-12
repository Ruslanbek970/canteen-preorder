import { act, fireEvent, screen, waitFor } from '@testing-library/react';

import type { KitchenBoard, KitchenOrder } from '@/api/types';

import { FakeWebSocket } from './setup';
import { makeMe, mockApi, renderApp } from './utils';

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

function card(extra: Partial<KitchenOrder> = {}): KitchenOrder {
  return {
    id: 1,
    order_number: 'A-007',
    status: 'paid',
    channel: 'mobile_app',
    pickup_slot_id: 7,
    pickup_shelf: null,
    paid_at: '2026-10-12T05:00:00Z',
    items: [{ menu_item_id: 1, name: 'Плов', quantity: 2 }],
    allergy_flag: 'АЛЛЕРГИЯ: ОРЕХИ',
    ...extra,
  };
}

function board(orders: KitchenOrder[]): KitchenBoard {
  return {
    canteen_id: 1,
    date: '2026-10-12',
    slots: [{ slot_id: 7, starts_at: '12:00:00', ends_at: '12:10:00', orders }],
    counts: {
      paid: orders.filter((o) => o.status === 'paid').length,
      cooking: orders.filter((o) => o.status === 'cooking').length,
      ready: orders.filter((o) => o.status === 'ready').length,
    },
  };
}

const prep = {
  canteen_id: 1,
  date: '2026-10-12',
  slots: [
    {
      slot_id: 7,
      starts_at: '12:00:00',
      ends_at: '12:10:00',
      orders: 1,
      items: [{ name: 'Плов', quantity: 14 }],
    },
  ],
};

describe('kitchen board', () => {
  it('shows the summary, columns, allergy line and moves an order on', async () => {
    const fetchMock = mockApi({
      '/me': makeMe('cook'),
      '/kitchen/board': board([
        card(),
        card({
          id: 2,
          order_number: 'A-008',
          status: 'ready',
          pickup_shelf: 3,
          allergy_flag: null,
        }),
      ]),
      '/kitchen/prep-summary': prep,
      '/kitchen/orders/1/status': card({ status: 'cooking' }),
    });
    renderApp('/kitchen', makeMe('cook'));
    expect(await screen.findByText('A-007')).toBeInTheDocument();
    expect(screen.getByText(/К 12:00 собрать/)).toBeInTheDocument();
    expect(screen.getByText('Плов × 14')).toBeInTheDocument();
    expect(screen.getByText('АЛЛЕРГИЯ: ОРЕХИ')).toBeInTheDocument();
    expect(screen.getByText('Полка 3')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'В работу' }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url).endsWith('/kitchen/orders/1/status') &&
            init?.body === JSON.stringify({ status: 'cooking' }),
        ),
      ).toBe(true),
    );
  });

  it('a paid order appears without reload', async () => {
    let orders: KitchenOrder[] = [];
    mockApi({
      '/me': makeMe('cook'),
      '/kitchen/board': () => board(orders),
      '/kitchen/prep-summary': { ...prep, slots: [] },
    });
    renderApp('/kitchen', makeMe('cook'));
    expect(await screen.findByText('Оплаченных заказов на сегодня пока нет.')).toBeInTheDocument();
    const socket = FakeWebSocket.instances.filter((s) => s.url.includes('/ws/kitchen/1')).at(-1);
    expect(socket).toBeDefined();
    orders = [card({ id: 9, order_number: 'A-009' })];
    act(() =>
      socket?.onmessage?.({ data: JSON.stringify({ type: 'order.paid', data: { order_id: 9 } }) }),
    );
    expect(await screen.findByText('A-009')).toBeInTheDocument();
  });

  it('prints 58×40 labels', async () => {
    const print = vi.fn();
    vi.stubGlobal('print', print);
    mockApi({
      '/me': makeMe('cook'),
      '/kitchen/orders/1/label': {
        order_id: 1,
        order_number: 'A-007',
        canteen_name: 'Главная столовая',
        service_date: '2026-10-12',
        starts_at: '12:00:00',
        ends_at: '12:10:00',
        items: [{ menu_item_id: 1, name: 'Плов', quantity: 2 }],
        allergy_flag: 'АЛЛЕРГИЯ: ОРЕХИ',
      },
    });
    renderApp('/kitchen/labels?ids=1', makeMe('cook'));
    expect(await screen.findByText('A-007')).toBeInTheDocument();
    expect(screen.getByText('АЛЛЕРГИЯ: ОРЕХИ')).toBeInTheDocument();
    await waitFor(() => expect(print).toHaveBeenCalled());
  });
});
