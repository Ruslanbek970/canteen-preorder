import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import { vi } from 'vitest';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';

import type { Me, Role } from '@/api/types';
import { routes } from '@/app/routes';
import { useAuthStore } from '@/features/auth/store';

export function makeMe(role: Role, extra: Partial<Me> = {}): Me {
  return {
    id: 1,
    full_name: 'Test User',
    email: `${role}@demo.kz`,
    phone: null,
    role,
    canteen_id: ['cook', 'cashier', 'canteen_manager'].includes(role) ? 1 : null,
    canteen_name: null,
    group_id: role === 'student' ? 1 : null,
    group_code: role === 'student' ? 'SE-2301' : null,
    preferred_language: 'ru',
    email_verified: true,
    health_data_consent_at: null,
    loyalty_points: 0,
    telegram_linked: false,
    marketing_opt_out: false,
    no_show_count_30d: 0,
    ...extra,
  };
}

type Handler = (url: string, init?: RequestInit) => unknown;

/** Mocks fetch: `handlers` maps a path prefix (after /api/v1) to a JSON body or a function. */
export function mockApi(handlers: Record<string, unknown | Handler>) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.toString();
    const path = url.replace(/^\/api\/v1/, '');
    const key = Object.keys(handlers)
      .filter((k) => path.startsWith(k))
      .sort((a, b) => b.length - a.length)[0];
    if (key === undefined) {
      return new Response(JSON.stringify({ error: { code: 'not_found', message: path } }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    const value = handlers[key];
    const body = typeof value === 'function' ? (value as Handler)(path, init) : value;
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}

export function renderApp(path: string, me?: Me) {
  if (me) useAuthStore.setState({ accessToken: 'token', refreshToken: 'refresh' });
  else useAuthStore.setState({ accessToken: null, refreshToken: null });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(routes, {
    initialEntries: [path],
    future: { v7_relativeSplatPath: true },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} future={{ v7_startTransition: true }} />
    </QueryClientProvider>,
  );
  return router;
}
