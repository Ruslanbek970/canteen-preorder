import { screen, waitFor } from '@testing-library/react';

import type { Role } from '@/api/types';
import { homeFor } from '@/features/auth/useMe';

import { makeMe, mockApi, renderApp } from './utils';

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe('routing and role guards', () => {
  it('sends anonymous users to the login page', async () => {
    mockApi({});
    renderApp('/menu');
    expect(await screen.findByRole('heading', { name: 'Вход' })).toBeInTheDocument();
  });

  it('shows not found for unknown paths', () => {
    mockApi({});
    renderApp('/nope');
    expect(screen.getByRole('heading', { name: 'Страница не найдена' })).toBeInTheDocument();
  });

  it.each<[Role, string]>([
    ['student', '/menu'],
    ['teacher', '/menu'],
    ['cook', '/kitchen'],
    ['cashier', '/pickup'],
    ['canteen_manager', '/manager'],
    ['admin', '/admin'],
  ])('%s lands on %s', async (role, home) => {
    expect(homeFor(role)).toBe(home);
    const me = makeMe(role);
    mockApi({ '/me': me });
    const router = renderApp('/', me);
    await waitFor(() => expect(router.state.location.pathname).toBe(home));
  });

  it('redirects a role away from a page it may not open', async () => {
    const me = makeMe('cook');
    mockApi({ '/me': me });
    const router = renderApp('/admin', me);
    await waitFor(() => expect(router.state.location.pathname).toBe('/kitchen'));
  });
});
