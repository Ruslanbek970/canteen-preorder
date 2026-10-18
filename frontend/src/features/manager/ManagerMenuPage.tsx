import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { apiGet, apiPatch, apiPut, qs } from '@/api/client';
import type { ManagerDish, ManagerMenu } from '@/api/types';
import {
  Alert,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingState,
  Select,
} from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';
import { addDays, todayLocal } from '@/lib/format';

import { ManagerShell } from './ManagerShell';

interface Row {
  dish_id: number;
  dish_name: string;
  category_name: string;
  price: string;
  planned_portions: string;
  menu_item_id: number | null;
  available: number | null;
  sold: number;
  forecast: number | null;
  forecast_model: string | null;
}

export function ManagerMenuPage() {
  const { t } = useTranslation();
  const [date, setDate] = useState(() => addDays(todayLocal(), 1));
  const menu = useQuery({
    queryKey: ['manager', 'menu', date],
    queryFn: () => apiGet<ManagerMenu>(`/manager/menu${qs({ date })}`),
  });
  return (
    <ManagerShell
      title={t('manager.menu.title')}
      actions={
        <Field label={t('manager.menu.date')}>
          <Input
            type="date"
            value={date}
            onChange={(e) => e.target.value && setDate(e.target.value)}
          />
        </Field>
      }
    >
      {menu.isPending ? (
        <LoadingState />
      ) : menu.isError ? (
        <ErrorState error={menu.error} onRetry={() => void menu.refetch()} />
      ) : (
        <MenuEditor key={`${date}-${menu.dataUpdatedAt}`} date={date} menu={menu.data} />
      )}
    </ManagerShell>
  );
}

function toRows(menu: ManagerMenu): Row[] {
  return menu.items.map((i) => ({
    dish_id: i.dish_id,
    dish_name: i.dish_name,
    category_name: i.category_name,
    price: String(Number(i.price)),
    planned_portions: String(i.planned_portions),
    menu_item_id: i.id,
    available: i.available_portions,
    sold: i.sold_portions,
    forecast: i.forecast_portions,
    forecast_model: i.forecast_model,
  }));
}

function MenuEditor({ date, menu }: { date: string; menu: ManagerMenu }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const dishes = useQuery({
    queryKey: ['manager', 'dishes'],
    queryFn: () => apiGet<ManagerDish[]>('/manager/dishes'),
  });
  const [rows, setRows] = useState<Row[]>(() => toRows(menu));
  const [toAdd, setToAdd] = useState('');
  const key = ['manager', 'menu', date];

  const save = useMutation({
    mutationFn: () =>
      apiPut<ManagerMenu>(`/manager/menu${qs({ date })}`, {
        items: rows.map((r) => ({
          dish_id: r.dish_id,
          price: r.price,
          planned_portions: Number(r.planned_portions),
        })),
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(key, data);
      void queryClient.invalidateQueries({ queryKey: ['menu'] });
    },
  });
  const adjust = useMutation({
    mutationFn: ({ id, available }: { id: number; available: number }) =>
      apiPatch<ManagerMenu>(`/manager/menu-items/${id}`, { available_portions: available }),
    onSuccess: (data) => queryClient.setQueryData(key, data),
  });

  const inMenu = new Set(rows.map((r) => r.dish_id));
  const candidates = (dishes.data ?? []).filter((d) => d.is_active && !inMenu.has(d.id));
  const update = (dishId: number, patch: Partial<Row>) =>
    setRows(rows.map((r) => (r.dish_id === dishId ? { ...r, ...patch } : r)));

  function addDish() {
    const dish = dishes.data?.find((d) => String(d.id) === toAdd);
    if (!dish) return;
    setRows([
      ...rows,
      {
        dish_id: dish.id,
        dish_name: dish.name_ru,
        category_name: dish.category_name,
        price: String(Number(dish.base_price)),
        planned_portions: '30',
        menu_item_id: null,
        available: null,
        sold: 0,
        forecast: null,
        forecast_model: null,
      },
    ]);
    setToAdd('');
  }

  return (
    <div className="space-y-4">
      {save.isError && <Alert>{errorMessage(save.error)}</Alert>}
      {adjust.isError && <Alert>{errorMessage(adjust.error)}</Alert>}
      {save.isSuccess && <Alert tone="success">{t('common.saved')}</Alert>}
      <Card className="overflow-x-auto p-0">
        {rows.length === 0 ? (
          <EmptyState>{t('manager.menu.empty')}</EmptyState>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left dark:bg-slate-800">
              <tr>
                <th className="p-2">{t('manager.dishes.name')}</th>
                <th className="p-2 text-right">{t('manager.menu.forecast')}</th>
                <th className="p-2">{t('manager.menu.planned')}</th>
                <th className="p-2">{t('manager.dishes.price')}</th>
                <th className="p-2 text-right">{t('manager.menu.sold')}</th>
                <th className="p-2">{t('manager.menu.available')}</th>
                <th className="p-2" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.dish_id} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="p-2">
                    {r.dish_name}
                    <div className="text-xs text-slate-500">{r.category_name}</div>
                  </td>
                  <td className="p-2 text-right" title={r.forecast_model ?? undefined}>
                    {r.forecast ?? '—'}
                  </td>
                  <td className="p-2">
                    <Input
                      aria-label={t('manager.menu.planned')}
                      className="w-24"
                      type="number"
                      min="0"
                      value={r.planned_portions}
                      onChange={(e) => update(r.dish_id, { planned_portions: e.target.value })}
                    />
                  </td>
                  <td className="p-2">
                    <Input
                      aria-label={t('manager.dishes.price')}
                      className="w-28"
                      type="number"
                      min="1"
                      value={r.price}
                      onChange={(e) => update(r.dish_id, { price: e.target.value })}
                    />
                  </td>
                  <td className="p-2 text-right">{r.sold}</td>
                  <td className="p-2">
                    {r.menu_item_id !== null && r.available !== null ? (
                      <AvailableInput
                        value={r.available}
                        onSave={(available) =>
                          adjust.mutate({ id: r.menu_item_id as number, available })
                        }
                      />
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="p-2 text-right">
                    <Button
                      variant="ghost"
                      aria-label={t('common.remove')}
                      onClick={() => setRows(rows.filter((x) => x.dish_id !== r.dish_id))}
                    >
                      ✕
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      <div className="flex flex-wrap items-end gap-2">
        {candidates.length > 0 ? (
          <>
            <Field label={t('manager.menu.addDish')}>
              <Select value={toAdd} onChange={(e) => setToAdd(e.target.value)}>
                <option value="">{t('manager.menu.chooseDish')}</option>
                {candidates.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name_ru}
                  </option>
                ))}
              </Select>
            </Field>
            <Button variant="secondary" onClick={addDish} disabled={!toAdd}>
              {t('common.add')}
            </Button>
          </>
        ) : (
          dishes.isSuccess && (
            <p className="text-sm text-slate-600">
              {t('manager.menu.allDishesInMenu')}{' '}
              <Link to="/manager/dishes" className="font-medium text-brand-700 underline">
                {t('manager.menu.newDish')}
              </Link>
            </p>
          )
        )}
        <Button className="ml-auto" onClick={() => save.mutate()} disabled={save.isPending}>
          {t('manager.menu.save')}
        </Button>
      </div>
      {menu.synthetic_history && (
        <p className="text-xs text-slate-500">{t('manager.syntheticNote')}</p>
      )}
    </div>
  );
}

function AvailableInput({ value, onSave }: { value: number; onSave: (v: number) => void }) {
  const { t } = useTranslation();
  const [v, setV] = useState(String(value));
  return (
    <div className="flex gap-1">
      <Input
        aria-label={t('manager.menu.available')}
        className="w-20"
        type="number"
        min="0"
        value={v}
        onChange={(e) => setV(e.target.value)}
      />
      {Number(v) !== value && (
        <Button variant="secondary" onClick={() => onSave(Number(v))}>
          OK
        </Button>
      )}
    </div>
  );
}
