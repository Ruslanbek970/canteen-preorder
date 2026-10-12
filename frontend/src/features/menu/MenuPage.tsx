import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Alert, EmptyState, LoadingState, PageTitle, Select } from '@/components/ui';
import { useMe } from '@/features/auth/useMe';
import { AddToCart } from '@/features/cart/AddToCart';
import { cartCount, useCartStore } from '@/features/cart/store';
import { cartTotals } from '@/features/cart/totals';
import { formatPrice } from '@/lib/format';

import { MenuView } from './MenuView';
import { useCanteen } from './useCanteen';

export function MenuPage() {
  const { t } = useTranslation();
  const me = useMe();
  const { canteens, list, current, select } = useCanteen();
  const lines = useCartStore((s) => s.lines);
  if (canteens.isPending) return <LoadingState />;
  if (!current) return <EmptyState>{t('menu.noCanteens')}</EmptyState>;
  return (
    <section className="p-4">
      <PageTitle
        actions={
          list.length > 1 ? (
            <Select
              aria-label={t('menu.canteen')}
              className="w-auto"
              value={current.id}
              onChange={(e) => select(Number(e.target.value))}
            >
              {list.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          ) : (
            <span className="text-sm text-slate-500">{current.name}</span>
          )
        }
      >
        {t('pages.menu')}
      </PageTitle>
      {me.data && !me.data.email_verified && (
        <div className="mb-3">
          <Alert tone="warning">{t('menu.verifyToOrder')}</Alert>
        </div>
      )}
      <MenuView
        canteenId={current.id}
        signedIn
        action={(item, date) => (
          <AddToCart
            item={item}
            canteenId={current.id}
            date={date}
            disabled={!me.data?.email_verified}
          />
        )}
      />
      {lines.length > 0 && (
        <div className="sticky bottom-0 -mx-4 mt-4 border-t border-slate-200 bg-white/95 p-3 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95">
          <Link
            to="/cart"
            className="flex min-h-[48px] items-center justify-between rounded-lg bg-green-600 px-4 font-medium text-white"
          >
            <span>{t('cart.openWith', { count: cartCount(lines) })}</span>
            <span>{formatPrice(cartTotals(lines).total)}</span>
          </Link>
        </div>
      )}
    </section>
  );
}
