import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import type { MenuItem } from '@/api/types';
import { Badge } from '@/components/ui';
import { formatPrice } from '@/lib/format';
import { allergenName, dishName } from '@/lib/names';

export function DishCard({ item, action }: { item: MenuItem; action?: ReactNode }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.resolvedLanguage;
  const soldOut = item.available_portions === 0;
  return (
    <article
      className={`flex flex-col rounded-2xl border bg-white p-4 shadow-sm transition duration-200 hover:shadow-lg motion-safe:hover:-translate-y-0.5 dark:bg-slate-900 ${
        item.unsafe_for_me
          ? 'border-red-400 ring-1 ring-red-300 dark:border-red-700'
          : 'border-slate-200 dark:border-slate-800'
      }`}
      aria-label={dishName(item, lang)}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold leading-tight">
          <Link to={`/dishes/${item.dish_id}`} className="hover:underline">
            {dishName(item, lang)}
          </Link>
        </h3>
        <div className="text-right">
          {item.discount_percent ? (
            <>
              <div className="text-sm text-slate-500 line-through">{formatPrice(item.price)}</div>
              <div className="font-semibold text-red-600">{formatPrice(item.price_now)}</div>
            </>
          ) : (
            <div className="font-semibold">{formatPrice(item.price)}</div>
          )}
        </div>
      </div>
      <div className="mt-1 flex flex-wrap gap-1">
        {item.discount_percent ? <Badge tone="red">−{item.discount_percent}%</Badge> : null}
        {item.is_halal && <Badge tone="green">{t('menu.halal')}</Badge>}
        {item.is_vegetarian && <Badge tone="green">{t('menu.vegetarian')}</Badge>}
        {item.rating !== null && (
          <Badge tone="amber">
            ★ {item.rating.toFixed(1)} ({item.rating_count})
          </Badge>
        )}
      </div>
      {item.description && (
        <p className="mt-2 line-clamp-2 text-sm text-slate-600 dark:text-slate-300">
          {item.description}
        </p>
      )}
      <p className="mt-2 text-xs text-slate-500">
        {[
          item.portion_grams ? t('menu.grams', { value: item.portion_grams }) : null,
          item.calories !== null ? t('menu.kcal', { value: item.calories }) : null,
          item.protein_g !== null
            ? t('menu.pfc', { p: item.protein_g, f: item.fat_g, c: item.carbs_g })
            : null,
        ]
          .filter(Boolean)
          .join(' · ')}
      </p>
      {item.allergens.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-1" aria-label={t('menu.allergens')}>
          {item.allergens.map((a) => {
            const mine = item.my_allergens.includes(a.code);
            return (
              <li key={a.id}>
                <Badge tone={mine ? (item.unsafe_for_me ? 'red' : 'amber') : 'gray'}>
                  {allergenName(a, lang)}
                </Badge>
              </li>
            );
          })}
        </ul>
      )}
      {item.unsafe_for_me && (
        <p className="mt-2 text-sm font-medium text-red-700 dark:text-red-300">
          {t('menu.unsafe')}
        </p>
      )}
      {!item.unsafe_for_me && item.warning_for_me && (
        <p className="mt-2 text-sm text-amber-700 dark:text-amber-300">{t('menu.warning')}</p>
      )}
      <div className="mt-auto flex items-center justify-between gap-2 pt-3">
        <span className={`text-sm ${soldOut ? 'text-red-600' : 'text-slate-500'}`}>
          {soldOut ? t('menu.soldOut') : t('menu.left', { count: item.available_portions })}
        </span>
        {action}
      </div>
    </article>
  );
}
