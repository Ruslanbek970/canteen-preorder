import { fireEvent, screen, waitFor } from '@testing-library/react';

import type { AppNotification, Promotion } from '@/api/types';

import { makeMe, mockApi, renderApp } from './utils';

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

const note = (extra: Partial<AppNotification>): AppNotification => ({
  id: 1,
  kind: 'order_ready',
  title: 'Заказ A-001 готов',
  body: 'Заберите на полке 3.',
  order_id: 7,
  promotion_id: null,
  sent_at: '2026-10-12T07:00:00Z',
  read_at: null,
  ...extra,
});

describe('notifications', () => {
  it('shows the unread count in the bell and marks a notification read on open', async () => {
    const reads: string[] = [];
    mockApi({
      '/me': makeMe('student'),
      '/notifications/1/read': (path: string) => {
        reads.push(path);
        return note({ read_at: '2026-10-12T07:01:00Z' });
      },
      '/notifications': {
        items: [
          note({}),
          note({
            id: 2,
            kind: 'leftover_discount',
            title: 'Скидка 30% на Самса',
            order_id: null,
            promotion_id: 4,
            read_at: '2026-10-12T06:00:00Z',
          }),
        ],
        unread: 1,
      },
      '/orders': { items: [] },
    });
    const router = renderApp('/notifications', makeMe('student'));
    expect(await screen.findByText('Заказ A-001 готов')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '1 непрочитанное уведомление' })).toBeInTheDocument();
    expect(screen.getByText('Скидка 30% на Самса')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Заказ A-001 готов'));
    await waitFor(() => expect(reads).toEqual(['/notifications/1/read']));
    expect(router.state.location.pathname).toBe('/orders/7');
  });

  it('has an empty state', async () => {
    mockApi({ '/me': makeMe('teacher'), '/notifications': { items: [], unread: 0 } });
    renderApp('/notifications', makeMe('teacher'));
    expect(await screen.findByText(/Уведомлений пока нет/)).toBeInTheDocument();
    expect(screen.queryByText('Прочитать все')).not.toBeInTheDocument();
  });

  it('shows a Telegram link code in the profile', async () => {
    mockApi({
      '/me/allergens': { health_data_consent_at: null, allergens: [] },
      '/me/telegram/link-code': {
        code: '123456',
        expires_in: 600,
        bot_username: 'canteen_bot',
        deep_link: 'https://t.me/canteen_bot?start=123456',
      },
      '/me': makeMe('student'),
      '/groups': [],
      '/allergens': [],
      '/notifications': { items: [], unread: 0 },
    });
    renderApp('/profile', makeMe('student'));
    fireEvent.click(await screen.findByText('Привязать Telegram'));
    expect(await screen.findByText('/start 123456')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Открыть @canteen_bot' })).toHaveAttribute(
      'href',
      'https://t.me/canteen_bot?start=123456',
    );
    expect(screen.getByText('Код действует 10 минут.')).toBeInTheDocument();
  });
});

const promotion = (extra: Partial<Promotion>): Promotion => ({
  id: 1,
  type: 'leftover',
  status: 'proposed',
  discount_percent: 30,
  valid_from: '2026-10-12T09:00:00Z',
  valid_to: '2026-10-12T10:00:00Z',
  created_by_system: true,
  created_at: '2026-10-12T09:00:00Z',
  menu_item_id: 3,
  dish_name: 'Самса',
  available_portions: 20,
  planned_portions: 40,
  pickup_slot_id: null,
  slot_date: null,
  slot_starts_at: null,
  slot_ends_at: null,
  slot_booked: null,
  slot_capacity: null,
  ...extra,
});

describe('manager promotions', () => {
  it('lists proposals and approves one', async () => {
    let approved = false;
    mockApi({
      '/me': makeMe('canteen_manager'),
      '/manager/promotions/1/approve': () => {
        approved = true;
        return promotion({ status: 'active' });
      },
      '/manager/promotions': () =>
        approved
          ? [promotion({ status: 'active' })]
          : [
              promotion({}),
              promotion({
                id: 2,
                type: 'off_peak',
                status: 'active',
                created_by_system: false,
                discount_percent: 15,
                dish_name: null,
                menu_item_id: null,
                pickup_slot_id: 9,
                slot_starts_at: '15:00:00',
                slot_ends_at: '15:10:00',
                slot_booked: 2,
                slot_capacity: 30,
              }),
            ],
      '/manager/slots': { canteen_id: 1, date: '2026-10-12', slots: [] },
    });
    renderApp('/manager/promotions', makeMe('canteen_manager'));
    expect(await screen.findByText('Самса')).toBeInTheDocument();
    expect(screen.getByText(/осталось 20 из 40 порций/)).toBeInTheDocument();
    expect(screen.getByText('Слот 15:00–15:10')).toBeInTheDocument();
    expect(await screen.findByText('На сегодня нет открытых слотов.')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Одобрить'));
    await waitFor(() => expect(screen.getByText('Новых предложений нет.')).toBeInTheDocument());
    expect(approved).toBe(true);
  });
});
