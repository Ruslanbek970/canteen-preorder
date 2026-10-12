import { fireEvent, screen, waitFor } from '@testing-library/react';

import type { PickupOrder } from '@/api/types';

import { menuItem } from './fixtures';
import { makeMe, mockApi, renderApp } from './utils';

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

function found(extra: Partial<PickupOrder> = {}): PickupOrder {
  return {
    id: 5,
    order_number: 'A-007',
    status: 'ready',
    pickup_shelf: 3,
    starts_at: '12:00:00',
    ends_at: '12:10:00',
    customer_name: 'Аружан Сапарова',
    items: [{ menu_item_id: 1, name: 'Плов', quantity: 2 }],
    total: '3000.00',
    allergy_flag: 'АЛЛЕРГИЯ: ОРЕХИ',
    picked_up_at: null,
    ...extra,
  };
}

describe('pickup', () => {
  it('finds an order by number and hands it over', async () => {
    const fetchMock = mockApi({
      '/me': makeMe('cashier'),
      '/pickup/by-number/7': found(),
      '/pickup/orders/5/confirm': found({ status: 'picked_up' }),
    });
    renderApp('/pickup', makeMe('cashier'));
    fireEvent.change(await screen.findByLabelText('Номер заказа'), { target: { value: '7' } });
    fireEvent.click(screen.getByRole('button', { name: 'Найти' }));
    expect(await screen.findByText('A-007')).toBeInTheDocument();
    expect(screen.getByTestId('shelf')).toHaveTextContent('3');
    expect(screen.getByText('АЛЛЕРГИЯ: ОРЕХИ')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Выдать' }));
    expect(await screen.findByText('Выдан')).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).endsWith('/pickup/orders/5/confirm')),
    ).toBe(true);
  });

  it('shows «Ещё готовится» in large type', async () => {
    mockApi({
      '/me': makeMe('cashier'),
      '/pickup/by-number/A-007': found({ status: 'cooking', pickup_shelf: null }),
    });
    renderApp('/pickup', makeMe('cashier'));
    fireEvent.change(await screen.findByLabelText('Номер заказа'), { target: { value: 'A-007' } });
    fireEvent.click(screen.getByRole('button', { name: 'Найти' }));
    expect(await screen.findByText('Ещё готовится')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Выдать' })).not.toBeInTheDocument();
  });
});

describe('pos', () => {
  it('sells from menu tiles', async () => {
    const fetchMock = mockApi({
      '/me': makeMe('cashier'),
      '/canteens/1/menu': {
        canteen_id: 1,
        date: '2026-10-12',
        available_dates: ['2026-10-12'],
        items: [menuItem({ id: 1, name_ru: 'Плов', price_now: '1500' })],
      },
      '/pos/sales': {
        order_id: 9,
        order_number: 'K-001',
        method: 'cash',
        subtotal: '3000.00',
        discount_total: '0.00',
        total: '3000.00',
        fiscal_receipt_number: 'MOCK-00000001',
        items: [],
      },
    });
    renderApp('/pos', makeMe('cashier'));
    const tile = await screen.findByRole('button', { name: /Плов/ });
    fireEvent.click(tile);
    fireEvent.click(tile);
    expect(screen.getByTestId('pos-total')).toHaveTextContent('3 000');
    fireEvent.click(screen.getByRole('button', { name: 'Продать' }));
    expect(await screen.findByText(/Продано: K-001/)).toBeInTheDocument();
    const post = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/pos/sales'));
    await waitFor(() =>
      expect(JSON.parse(String(post?.[1]?.body))).toEqual({
        items: [{ menu_item_id: 1, quantity: 2 }],
        method: 'cash',
      }),
    );
  });
});
