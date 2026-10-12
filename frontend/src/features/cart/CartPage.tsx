import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { ApiError } from '@/api/client';
import type { RepeatResponse } from '@/api/types';
import {
  Alert,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  PageTitle,
} from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';
import { useMe } from '@/features/auth/useMe';
import { useCreateOrder, useSlots } from '@/features/orders/api';
import { formatDay, formatPrice, todayLocal } from '@/lib/format';
import { dishName } from '@/lib/names';
import { useOnline } from '@/lib/pwa';

import { SlotPicker } from './SlotPicker';
import { MAX_QUANTITY, useCartStore } from './store';
import { cartTotals } from './totals';

export function CartPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const errorMessage = useErrorMessage();
  const me = useMe();
  const { canteenId, date, slotId, lines, setQuantity, setSlot, clear } = useCartStore();
  const slots = useSlots(canteenId, date);
  const create = useCreateOrder();
  const online = useOnline();
  const [ack, setAck] = useState(false);
  const skipped = (useLocation().state as { skipped?: RepeatResponse['skipped'] } | null)?.skipped;

  if (lines.length === 0 || !canteenId || !date) {
    return (
      <section className="p-4">
        <PageTitle>{t('cart.title')}</PageTitle>
        <EmptyState>
          {t('cart.empty')}{' '}
          <Link to="/menu" className="text-brand-700 underline dark:text-brand-400">
            {t('cart.toMenu')}
          </Link>
        </EmptyState>
      </section>
    );
  }

  const slot = slots.data?.slots.find((s) => s.id === slotId) ?? null;
  const totals = cartTotals(lines, slot?.discount_percent ?? null);
  const needsAck = lines.some((l) => l.warning);
  const canSubmit =
    online &&
    Boolean(slot) &&
    (!needsAck || ack) &&
    Boolean(me.data?.email_verified) &&
    !create.isPending;

  const submit = () => {
    if (!slot) return;
    create.mutate(
      {
        canteen_id: canteenId,
        pickup_slot_id: slot.id,
        items: lines.map((l) => ({ menu_item_id: l.menuItemId, quantity: l.quantity })),
        allergy_warning_ack: ack,
      },
      {
        onSuccess: (order) => {
          clear();
          navigate(order.payment_url ?? `/orders/${order.id}`);
        },
        onError: (error) => {
          if (error instanceof ApiError && error.code === 'slot_unavailable') setSlot(null);
        },
      },
    );
  };

  return (
    <section className="p-4">
      <PageTitle
        actions={
          <Button variant="ghost" onClick={clear}>
            {t('cart.clear')}
          </Button>
        }
      >
        {t('cart.title')}
      </PageTitle>
      <p className="mb-3 text-sm text-slate-500">
        {date === todayLocal() ? t('menu.today') : t('menu.tomorrow')} · {formatDay(date)}
      </p>

      {skipped && skipped.length > 0 && (
        <div className="mb-3">
          <Alert tone="info">
            {t('cart.skipped')}{' '}
            {skipped.map((s) => `${s.name_ru} (${t(`cart.skipReason.${s.reason}`)})`).join(', ')}
          </Alert>
        </div>
      )}
      <Card className="mb-4">
        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
          {lines.map((line) => (
            <li key={line.menuItemId} className="flex items-center justify-between gap-2 py-3">
              <div className="min-w-0">
                <div className="truncate font-medium">
                  {dishName({ name_ru: line.nameRu, name_kk: line.nameKk }, i18n.resolvedLanguage)}
                </div>
                <div className="text-sm text-slate-500">
                  {formatPrice(line.price)}
                  {line.discountPercent ? ` · −${line.discountPercent}%` : ''}
                </div>
                {line.warning && (
                  <div className="text-xs text-amber-700 dark:text-amber-300">
                    {t('menu.warning')}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2" role="group" aria-label={line.nameRu}>
                <Button
                  variant="secondary"
                  aria-label={t('cart.decrease')}
                  onClick={() => setQuantity(line.menuItemId, line.quantity - 1)}
                >
                  −
                </Button>
                <span className="min-w-6 text-center font-semibold">{line.quantity}</span>
                <Button
                  variant="secondary"
                  aria-label={t('cart.increase')}
                  disabled={line.quantity >= Math.min(MAX_QUANTITY, line.available)}
                  onClick={() => setQuantity(line.menuItemId, line.quantity + 1)}
                >
                  +
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </Card>

      <Card className="mb-4">
        {slots.isPending ? (
          <LoadingState />
        ) : slots.isError ? (
          <ErrorState error={slots.error} onRetry={() => void slots.refetch()} />
        ) : (
          <SlotPicker data={slots.data} value={slotId} onChange={setSlot} />
        )}
      </Card>

      <Card className="mb-4">
        <dl className="space-y-1">
          <div className="flex justify-between">
            <dt>{t('cart.subtotal')}</dt>
            <dd>{formatPrice(totals.subtotal)}</dd>
          </div>
          {totals.discount > 0 && (
            <div className="flex justify-between text-red-600">
              <dt>{t('cart.discount')}</dt>
              <dd>−{formatPrice(totals.discount)}</dd>
            </div>
          )}
          <div className="flex justify-between text-lg font-semibold">
            <dt>{t('cart.total')}</dt>
            <dd data-testid="cart-total">{formatPrice(totals.total)}</dd>
          </div>
        </dl>
      </Card>

      {needsAck && (
        <label className="mb-4 flex items-start gap-3 rounded-lg bg-amber-50 p-3 text-sm dark:bg-amber-950">
          <input
            type="checkbox"
            className="mt-0.5 h-5 w-5"
            checked={ack}
            onChange={(e) => setAck(e.target.checked)}
          />
          {t('cart.allergyAck')}
        </label>
      )}
      {!me.data?.email_verified && (
        <div className="mb-3">
          <Alert tone="warning">{t('menu.verifyToOrder')}</Alert>
        </div>
      )}
      {create.isError && (
        <div className="mb-3">
          <Alert tone="error">{errorMessage(create.error)}</Alert>
        </div>
      )}
      <Button className="w-full" disabled={!canSubmit} onClick={submit}>
        {create.isPending
          ? t('cart.placing')
          : !online
            ? t('pwa.offlineShort')
            : slot
              ? t('cart.place', { total: formatPrice(totals.total) })
              : t('cart.chooseSlot')}
      </Button>
    </section>
  );
}
