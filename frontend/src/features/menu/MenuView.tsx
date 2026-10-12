import { type ReactNode, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import type { MenuItem } from '@/api/types';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui';
import { formatDay } from '@/lib/format';

import { DishCard } from './DishCard';
import { DEFAULT_FILTERS, type MenuFilters, categoriesOf, filterMenu } from './filters';
import { useMenu } from './useMenu';

interface Props {
  canteenId: number;
  signedIn: boolean;
  action?: (item: MenuItem, date: string) => ReactNode;
}

/** Menu with date switch, category tabs and filters; shared by the student and public pages. */
export function MenuView({ canteenId, signedIn, action }: Props) {
  const { t } = useTranslation();
  const [date, setDate] = useState<string | undefined>(undefined);
  const [filters, setFilters] = useState<MenuFilters>(DEFAULT_FILTERS);
  const menu = useMenu(canteenId, date);
  const items = useMemo(() => menu.data?.items ?? [], [menu.data]);
  const categories = useMemo(() => categoriesOf(items), [items]);
  const visible = useMemo(() => filterMenu(items, filters), [items, filters]);

  if (menu.isPending) return <LoadingState />;
  if (menu.isError) return <ErrorState error={menu.error} onRetry={() => void menu.refetch()} />;

  const toggle = (key: 'safeForMe' | 'halal' | 'vegetarian') =>
    setFilters((f) => ({ ...f, [key]: !f[key] }));

  return (
    <div>
      {menu.data.available_dates.length > 1 && (
        <div className="mb-3 flex gap-2" role="tablist" aria-label={t('menu.date')}>
          {menu.data.available_dates.map((d, idx) => (
            <button
              key={d}
              type="button"
              role="tab"
              aria-selected={menu.data.date === d}
              className={`rounded-full px-4 py-2 text-sm ${
                menu.data.date === d ? 'bg-green-600 text-white' : 'bg-slate-100 dark:bg-slate-800'
              }`}
              onClick={() => setDate(idx === 0 ? undefined : d)}
            >
              {idx === 0 ? t('menu.today') : t('menu.tomorrow')} · {formatDay(d)}
            </button>
          ))}
        </div>
      )}
      <div
        className="-mx-4 mb-3 overflow-x-auto px-4"
        role="tablist"
        aria-label={t('menu.categories')}
      >
        <div className="flex gap-2">
          {[{ id: null, name: t('menu.all') }, ...categories].map((c) => (
            <button
              key={c.id ?? 'all'}
              type="button"
              role="tab"
              aria-selected={filters.categoryId === c.id}
              className={`whitespace-nowrap rounded-lg border px-3 py-1.5 text-sm ${
                filters.categoryId === c.id
                  ? 'border-green-600 bg-green-50 text-green-800 dark:bg-green-950 dark:text-green-200'
                  : 'border-slate-200 dark:border-slate-700'
              }`}
              onClick={() => setFilters((f) => ({ ...f, categoryId: c.id }))}
            >
              {c.name}
            </button>
          ))}
        </div>
      </div>
      <div className="mb-4 flex flex-wrap gap-3 text-sm">
        {signedIn && (
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              className="h-5 w-5"
              checked={filters.safeForMe}
              onChange={() => toggle('safeForMe')}
            />
            {t('menu.withoutMyAllergens')}
          </label>
        )}
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            className="h-5 w-5"
            checked={filters.halal}
            onChange={() => toggle('halal')}
          />
          {t('menu.halal')}
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            className="h-5 w-5"
            checked={filters.vegetarian}
            onChange={() => toggle('vegetarian')}
          />
          {t('menu.vegetarian')}
        </label>
      </div>
      {items.length === 0 ? (
        <EmptyState>{t('menu.empty')}</EmptyState>
      ) : visible.length === 0 ? (
        <EmptyState>{t('menu.nothingMatches')}</EmptyState>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((item) => (
            <DishCard key={item.id} item={item} action={action?.(item, menu.data.date)} />
          ))}
        </div>
      )}
    </div>
  );
}
