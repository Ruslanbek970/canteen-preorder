import { fireEvent, screen, waitFor } from '@testing-library/react';

import type { Ingredient } from '@/api/types';

import { makeMe, mockApi, renderApp } from './utils';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
});

describe('manager catalog delete', () => {
  it('deletes an ingredient after confirmation and reloads the list', async () => {
    let list: Ingredient[] = [
      { id: 1, name: 'рис', unit: 'g', allergens: [] },
      { id: 2, name: 'мука', unit: 'g', allergens: [] },
    ];
    const deleted: string[] = [];
    mockApi({
      '/me': makeMe('canteen_manager'),
      '/allergens': [],
      '/manager/ingredients': (path: string, init?: RequestInit) => {
        if (init?.method === 'DELETE') {
          deleted.push(path);
          list = list.filter((i) => `/manager/ingredients/${i.id}` !== path);
          return null;
        }
        return list;
      },
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderApp('/manager/ingredients', makeMe('canteen_manager'));
    expect(await screen.findByText('рис')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Удалить: рис' }));
    await waitFor(() => expect(deleted).toEqual(['/manager/ingredients/1']));
    expect(await screen.findByText('Удалено')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText('рис')).not.toBeInTheDocument());
    expect(screen.getByText('мука')).toBeInTheDocument();
  });

  it('shows the server reason when a dish cannot be deleted', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input).replace(/^\/api\/v1/, '');
        const json = (body: unknown, status = 200) =>
          new Response(JSON.stringify(body), {
            status,
            headers: { 'Content-Type': 'application/json' },
          });
        if (path === '/me') return json(makeMe('canteen_manager'));
        if (init?.method === 'DELETE')
          return json({ error: { code: 'dish_in_use', message: 'in use', details: {} } }, 409);
        if (path === '/manager/dishes')
          return json([
            {
              id: 7,
              category_id: 1,
              category_name: 'Горячее',
              name_ru: 'Плов',
              name_kk: null,
              description: null,
              base_price: '1500.00',
              portion_grams: null,
              calories: null,
              protein_g: null,
              fat_g: null,
              carbs_g: null,
              shelf_life_hours: 4,
              is_halal: true,
              is_vegetarian: false,
              photo_url: null,
              is_active: true,
              ingredients: [],
              allergens: [],
            },
          ]);
        return json([]);
      }),
    );
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderApp('/manager/dishes', makeMe('canteen_manager'));
    fireEvent.click(await screen.findByRole('button', { name: 'Удалить: Плов' }));
    expect(await screen.findByText(/Выключите его вместо удаления/)).toBeInTheDocument();
  });
});
