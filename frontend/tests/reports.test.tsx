import { fireEvent, screen, waitFor } from '@testing-library/react';

import type { Dashboard, RatingsReport, SalesReport } from '@/api/types';
import { lastDays } from '@/features/manager/reportsApi';

import { makeMe, mockApi, renderApp } from './utils';

// Recharts' ResponsiveContainer needs ResizeObserver, which jsdom lacks.
class FakeResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  vi.stubGlobal('ResizeObserver', FakeResizeObserver);
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

const dashboard: Dashboard = {
  date: '2026-10-12',
  orders_total: 9,
  orders_by_status: {
    pending_payment: 1,
    paid: 2,
    cooking: 1,
    ready: 1,
    picked_up: 3,
    cancelled: 0,
    no_show: 1,
  },
  preorders: 6,
  cashier_sales: 2,
  revenue: '12500.00',
  portions_sold: 14,
  waste_portions: 4,
  waste_by_reason: { expired: 3, uncollected_order: 1, damaged: 0, other: 0 },
  no_show: 1,
  no_show_percent: 25,
  proposed_promotions: 2,
  slots: [
    {
      id: 1,
      starts_at: '12:00:00',
      ends_at: '12:10:00',
      capacity: 30,
      booked: 30,
      is_closed: false,
    },
    {
      id: 2,
      starts_at: '12:10:00',
      ends_at: '12:20:00',
      capacity: 30,
      booked: 3,
      is_closed: false,
    },
  ],
  synthetic_history_until: '2026-10-09',
};

const sales: SalesReport = {
  from_date: '2026-09-15',
  to_date: '2026-10-12',
  totals: {
    orders: 700,
    portions: 1300,
    revenue: '1050000.00',
    average_check: '1500.00',
    preorder_share: 55.5,
  },
  days: [
    { date: '2026-10-08', orders: 350, portions: 650, revenue: '520000.00', preorder_share: 55 },
    { date: '2026-10-09', orders: 350, portions: 650, revenue: '530000.00', preorder_share: 56 },
  ],
  dishes: [{ dish_id: 4, name: 'Плов', portions: 170, revenue: '255000.00' }],
  synthetic_history_until: '2026-10-09',
};

const ratings: RatingsReport = {
  from_date: '2026-08-18',
  to_date: '2026-10-12',
  dishes: [
    {
      dish_id: 4,
      name: 'Плов',
      rating: 4.6,
      count: 20,
      distribution: [0, 0, 2, 4, 14],
      last_comments: [{ rating: 5, comment: 'Как дома!', created_at: '2026-10-09T08:00:00Z' }],
    },
  ],
  synthetic_history_until: null,
};

describe('manager dashboard', () => {
  it('shows today in numbers and slot load', async () => {
    mockApi({ '/me': makeMe('canteen_manager'), '/manager/dashboard': dashboard });
    renderApp('/manager', makeMe('canteen_manager'));
    expect(await screen.findByText(/12\s500\s₸/)).toBeInTheDocument();
    expect(screen.getByText('предзаказ 6 · касса 2')).toBeInTheDocument();
    expect(screen.getByText('25%')).toBeInTheDocument();
    expect(screen.getByTitle('12:00 · 30/30')).toBeInTheDocument();
    expect(screen.getByText(/Данные до 09\.10 включительно синтетические/)).toBeInTheDocument();
  });
});

describe('reports', () => {
  it('shows sales with the synthetic note, switches tabs and periods', async () => {
    const fetchMock = mockApi({
      '/me': makeMe('canteen_manager'),
      '/manager/reports/sales': sales,
      '/manager/reports/ratings': ratings,
      '/manager/reports/waste': {
        from_date: '2026-09-15',
        to_date: '2026-10-12',
        total: 0,
        per_day: null,
        percent_of_planned: null,
        by_reason: { expired: 0, uncollected_order: 0, damaged: 0, other: 0 },
        days: [],
        dishes: [],
        synthetic_history_until: null,
      },
    });
    renderApp('/manager/reports', makeMe('canteen_manager'));
    expect(await screen.findByText(/1\s050\s000\s₸/)).toBeInTheDocument();
    expect(screen.getByText('55.5%')).toBeInTheDocument();
    expect(screen.getByText(/синтетические/)).toBeInTheDocument();
    const { from, to } = lastDays(28);
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/manager/reports/sales?from=${from}&to=${to}`,
      expect.anything(),
    );

    fireEvent.click(screen.getByRole('button', { name: '7 дней' }));
    const week = lastDays(7);
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        `/api/v1/manager/reports/sales?from=${week.from}&to=${week.to}`,
        expect.anything(),
      ),
    );

    fireEvent.click(screen.getByRole('tab', { name: 'Списания' }));
    expect(await screen.findByText('За этот период данных нет.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Оценки' }));
    expect(await screen.findByText('★ 4.6')).toBeInTheDocument();
    expect(screen.getByText('20 отзывов')).toBeInTheDocument();
    expect(screen.getByText(/Как дома!/)).toBeInTheDocument();
  });

  it('is closed to students', async () => {
    mockApi({ '/me': makeMe('student') });
    renderApp('/manager/reports', makeMe('student'));
    await waitFor(() => expect(screen.queryByText('Отчёты')).not.toBeInTheDocument());
  });
});
