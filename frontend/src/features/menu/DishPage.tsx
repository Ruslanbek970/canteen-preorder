import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';

import { apiGet } from '@/api/client';
import type { DishDetail } from '@/api/types';
import { Alert, Badge, Button, Card, ErrorState, LoadingState } from '@/components/ui';
import { allergenName, dishName } from '@/lib/names';
import { formatPrice } from '@/lib/format';

const UNITS: Record<string, string> = { g: 'units.g', ml: 'units.ml', pcs: 'units.pcs' };

export function DishPage() {
  const { t, i18n } = useTranslation();
  const lang = i18n.resolvedLanguage;
  const navigate = useNavigate();
  const { id = '' } = useParams();
  const dish = useQuery({
    queryKey: ['dish', id],
    queryFn: () => apiGet<DishDetail>(`/dishes/${id}`),
  });
  if (dish.isPending) return <LoadingState />;
  if (dish.isError) return <ErrorState error={dish.error} onRetry={() => void dish.refetch()} />;
  const d = dish.data;
  return (
    <section className="mx-auto max-w-2xl space-y-4 p-4">
      <Button variant="ghost" onClick={() => navigate(-1)}>
        ← {t('common.back')}
      </Button>
      {d.photo_url && (
        <img
          src={d.photo_url}
          alt={dishName(d, lang)}
          className="h-56 w-full rounded-xl object-cover"
        />
      )}
      <div className="flex items-start justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">{dishName(d, lang)}</h1>
          <p className="text-sm text-slate-500">{d.category_name}</p>
        </div>
        <div className="text-xl font-semibold">{formatPrice(d.base_price)}</div>
      </div>
      <div className="flex flex-wrap gap-1">
        {d.is_halal && <Badge tone="green">{t('menu.halal')}</Badge>}
        {d.is_vegetarian && <Badge tone="green">{t('menu.vegetarian')}</Badge>}
        {d.rating !== null && (
          <Badge tone="amber">
            ★ {d.rating.toFixed(1)} ({d.rating_count})
          </Badge>
        )}
      </div>
      {d.unsafe_for_me && <Alert>{t('menu.unsafe')}</Alert>}
      {!d.unsafe_for_me && d.warning_for_me && <Alert tone="warning">{t('menu.warning')}</Alert>}
      {d.description && <p>{d.description}</p>}
      <Card>
        <h2 className="mb-2 font-medium">{t('menu.nutrition')}</h2>
        <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-5">
          <div>
            <dt className="text-slate-500">{t('menu.weight')}</dt>
            <dd>
              {d.portion_grams ?? '—'} {t('units.g')}
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">{t('menu.calories')}</dt>
            <dd>{d.calories ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-slate-500">{t('menu.protein')}</dt>
            <dd>{d.protein_g ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-slate-500">{t('menu.fat')}</dt>
            <dd>{d.fat_g ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-slate-500">{t('menu.carbs')}</dt>
            <dd>{d.carbs_g ?? '—'}</dd>
          </div>
        </dl>
      </Card>
      <Card>
        <h2 className="mb-2 font-medium">{t('menu.ingredients')}</h2>
        <ul className="text-sm">
          {d.ingredients.map((i) => (
            <li key={i.ingredient_id}>
              {i.name} — {Number(i.quantity)} {t(UNITS[i.unit] ?? 'units.g')}
            </li>
          ))}
        </ul>
        <h2 className="mb-2 mt-4 font-medium">{t('menu.allergens')}</h2>
        {d.allergens.length === 0 ? (
          <p className="text-sm text-slate-500">{t('menu.noAllergens')}</p>
        ) : (
          <div className="flex flex-wrap gap-1">
            {d.allergens.map((a) => (
              <Badge key={a.id}>{allergenName(a, lang)}</Badge>
            ))}
          </div>
        )}
      </Card>
      <Card>
        <h2 className="mb-2 font-medium">{t('menu.reviews')}</h2>
        {d.reviews.length === 0 ? (
          <p className="text-sm text-slate-500">{t('menu.noReviews')}</p>
        ) : (
          <ul className="space-y-2">
            {d.reviews.map((r, idx) => (
              <li key={idx} className="text-sm">
                <span className="text-amber-600">{'★'.repeat(r.rating)}</span>
                {r.comment && <span className="ml-2">{r.comment}</span>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </section>
  );
}
