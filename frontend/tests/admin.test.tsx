import { fireEvent, screen, waitFor } from '@testing-library/react';

import type { AdminUser, ScheduleImportResult } from '@/api/types';

import { makeMe, mockApi, renderApp } from './utils';

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

const user = (extra: Partial<AdminUser>): AdminUser => ({
  id: 5,
  full_name: 'Айгуль Повар',
  email: 'cook@demo.kz',
  phone: null,
  role: 'cook',
  group_id: null,
  group_code: null,
  canteen_id: 1,
  canteen_name: 'Главная столовая',
  is_active: true,
  email_verified: true,
  created_at: '2026-10-01T00:00:00Z',
  ...extra,
});

describe('admin', () => {
  it('lists users, searches and blocks one', async () => {
    const patches: unknown[] = [];
    const fetchMock = mockApi({
      '/me': makeMe('admin'),
      '/admin/users/5': (_path: string, init?: RequestInit) => {
        patches.push(JSON.parse(String(init?.body)));
        return user({ is_active: false });
      },
      '/admin/users': { items: [user({})], total: 1 },
      '/admin/canteens': [],
      '/admin/groups': [],
    });
    renderApp('/admin', makeMe('admin'));
    expect(await screen.findByText('Айгуль Повар')).toBeInTheDocument();
    expect(screen.getByText(/cook@demo\.kz · Повар · Главная столовая/)).toBeInTheDocument();
    expect(screen.getByText('Найден 1 пользователь')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Поиск'), { target: { value: 'айгуль' } });
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/v1/admin/users?q=%D0%B0%D0%B9%D0%B3%D1%83%D0%BB%D1%8C&limit=50&offset=0',
        expect.anything(),
      ),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Изменить' }));
    fireEvent.click(screen.getByRole('button', { name: 'Заблокировать' }));
    await waitFor(() => expect(patches).toEqual([{ is_active: false }]));
  });

  it('checks a timetable file, shows errors, then imports a good one', async () => {
    const bad: ScheduleImportResult = {
      rows: 2,
      groups: [],
      errors: [{ line: 3, code: 'unknown_group', message: 'Группа «XX» не найдена' }],
      imported: false,
      deleted: 0,
      created: 0,
    };
    const good: ScheduleImportResult = {
      rows: 2,
      groups: ['SE-2301'],
      errors: [],
      imported: false,
      deleted: 4,
      created: 2,
    };
    const calls: string[] = [];
    let attempt = 0;
    mockApi({
      '/me': makeMe('admin'),
      '/admin/schedule/import': (path: string) => {
        calls.push(path);
        attempt += 1;
        if (attempt === 1) return bad;
        return path.endsWith('dry_run=true') ? good : { ...good, imported: true };
      },
    });
    renderApp('/admin/schedule', makeMe('admin'));
    const input = await screen.findByLabelText('Файл расписания');
    const file = new File(['group_code,...'], 'schedule.csv', { type: 'text/csv' });
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: 'Проверить' }));
    expect(await screen.findByText('В файле 1 ошибка, ничего не сохранено.')).toBeInTheDocument();
    expect(screen.getByText(/Такой группы нет/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Импортировать' })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'Проверить' }));
    expect(await screen.findByText(/Ошибок нет, можно импортировать/)).toBeInTheDocument();
    expect(screen.getByText(/Старых пар удалится: 4, новых: 2/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Импортировать' }));
    expect(await screen.findByText(/Расписание загружено/)).toBeInTheDocument();
    expect(calls).toEqual([
      '/admin/schedule/import?dry_run=true',
      '/admin/schedule/import?dry_run=true',
      '/admin/schedule/import?dry_run=false',
    ]);
  });

  it('shows groups with their timetable size', async () => {
    mockApi({
      '/me': makeMe('admin'),
      '/admin/groups': [
        { id: 1, code: 'SE-2301', faculty: 'ИТ', study_year: 3, students: 25, lessons: 14 },
      ],
    });
    renderApp('/admin/groups', makeMe('admin'));
    expect(await screen.findByText('SE-2301')).toBeInTheDocument();
    expect(screen.getByText('14')).toBeInTheDocument();
  });
});
