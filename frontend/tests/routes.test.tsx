import { render, screen } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';

import { routes } from '@/app/routes';

function renderAt(path: string) {
  const router = createMemoryRouter(routes, {
    initialEntries: [path],
    future: { v7_relativeSplatPath: true },
  });
  render(<RouterProvider router={router} future={{ v7_startTransition: true }} />);
}

describe('routing', () => {
  it.each([
    ['/menu', 'Меню'],
    ['/kitchen', 'Экран кухни'],
    ['/pickup', 'Выдача заказов'],
    ['/manager', 'Панель заведующей'],
    ['/admin', 'Администрирование'],
  ])('renders the placeholder page for %s', (path, title) => {
    renderAt(path);
    expect(screen.getByRole('heading', { name: title })).toBeInTheDocument();
  });

  it('shows not found for unknown paths', () => {
    renderAt('/nope');
    expect(screen.getByRole('heading', { name: 'Страница не найдена' })).toBeInTheDocument();
  });
});
