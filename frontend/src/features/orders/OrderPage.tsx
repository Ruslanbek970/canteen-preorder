import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { Alert, Button, Card, ErrorState, LoadingState } from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';
import { formatClock, formatDay, formatDayTime, formatPrice, formatTime } from '@/lib/format';
import { dishName } from '@/lib/names';

import { useCancelOrder, useOrder, usePayOrder } from './api';
import { OrderQr } from './OrderQr';
import { ReviewForm } from './ReviewForm';
import { StatusBadge } from './StatusBadge';
import { useRepeat } from './useRepeat';

export function OrderPage() {
  const { t, i18n } = useTranslation();
  const id = Number(useParams().id);
  const order = useOrder(id);
  const cancel = useCancelOrder();
  const repeat = useRepeat();
  const pay = usePayOrder();
  const navigate = useNavigate();
  const errorMessage = useErrorMessage();

  if (order.isPending) return <LoadingState />;
  if (order.isError)
    return (
      <section className="p-4">
        <ErrorState error={order.error} onRetry={() => void order.refetch()} />
      </section>
    );
  const o = order.data;
  const slot = o.pickup_slot;

  return (
    <section className="mx-auto max-w-xl p-4">
      <Link to="/orders" className="text-sm text-green-700 dark:text-green-400">
        ← {t('pages.orders')}
      </Link>
      <div className="mt-2 flex items-start justify-between gap-2">
        <div>
          <p className="text-sm text-slate-500">{t('orders.number')}</p>
          <h1 className="text-4xl font-bold tracking-wide">{o.order_number}</h1>
        </div>
        <StatusBadge status={o.status} />
      </div>
      <p className="mt-1 text-slate-600 dark:text-slate-300">
        {o.canteen_name}
        {slot &&
          ` · ${formatDay(slot.slot_date)} · ${formatClock(slot.starts_at)}–${formatClock(slot.ends_at)}`}
      </p>

      <div className="mt-3 space-y-2">
        {o.no_show_warning && <Alert tone="warning">{t('orders.noShowWarning')}</Alert>}
        {o.status === 'pending_payment' && (
          <Alert tone="info">
            {o.pay_until
              ? t('orders.payUntil', { time: formatTime(o.pay_until) })
              : t('orders.awaitingPayment')}
          </Alert>
        )}
        {o.status === 'ready' && o.pickup_shelf !== null && (
          <Alert tone="success">{t('orders.readyOnShelf', { shelf: o.pickup_shelf })}</Alert>
        )}
      </div>

      {o.status === 'pending_payment' && (
        <div className="mt-4">
          {o.payment_url ? (
            <Link
              to={o.payment_url}
              className="flex min-h-[48px] w-full items-center justify-center rounded-lg bg-green-700 px-4 font-medium text-white"
            >
              {t('orders.pay', { total: formatPrice(o.total) })}
            </Link>
          ) : (
            <Button
              className="w-full"
              disabled={pay.isPending}
              onClick={() => pay.mutate(o.id, { onSuccess: (p) => p.url && navigate(p.url) })}
            >
              {t('orders.payAgain', { total: formatPrice(o.total) })}
            </Button>
          )}
          {pay.isError && (
            <div className="mt-2">
              <Alert tone="error">{errorMessage(pay.error)}</Alert>
            </div>
          )}
        </div>
      )}
      {['paid', 'cooking', 'ready'].includes(o.status) && (
        <Card className="mt-4">
          <OrderQr token={o.qr_token} />
        </Card>
      )}

      <Card className="mt-4">
        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
          {o.items.map((item) => (
            <li key={item.id} className="flex justify-between gap-2 py-2">
              <span>
                {dishName(item, i18n.resolvedLanguage)} × {item.quantity}
              </span>
              <span className="text-right">
                {Number(item.discount_amount) > 0 && (
                  <span className="mr-2 text-sm text-slate-500 line-through">
                    {formatPrice(Number(item.unit_price) * item.quantity)}
                  </span>
                )}
                {formatPrice(item.line_total)}
              </span>
            </li>
          ))}
        </ul>
        <dl className="mt-2 space-y-1 border-t border-slate-100 pt-2 dark:border-slate-800">
          {Number(o.discount_total) > 0 && (
            <div className="flex justify-between text-red-600">
              <dt>{t('cart.discount')}</dt>
              <dd>−{formatPrice(o.discount_total)}</dd>
            </div>
          )}
          <div className="flex justify-between text-lg font-semibold">
            <dt>{t('cart.total')}</dt>
            <dd>{formatPrice(o.total)}</dd>
          </div>
        </dl>
      </Card>

      {o.review_until && (
        <Card className="mt-4">
          <h2 className="font-semibold">{t('reviews.title')}</h2>
          <p className="mb-3 text-sm text-slate-500">
            {t('reviews.until', { time: `${formatDayTime(o.review_until)}` })}
          </p>
          <div className="space-y-4">
            {o.items.map((item) => (
              <ReviewForm key={item.id} item={item} />
            ))}
          </div>
        </Card>
      )}

      <ol className="mt-4 space-y-1 text-sm text-slate-500">
        <li>
          {t('orders.createdAt')}: {formatTime(o.created_at)}
        </li>
        {o.paid_at && (
          <li>
            {t('orders.paidAt')}: {formatTime(o.paid_at)}
          </li>
        )}
        {o.ready_at && (
          <li>
            {t('orders.readyAt')}: {formatTime(o.ready_at)}
          </li>
        )}
        {o.picked_up_at && (
          <li>
            {t('orders.pickedUpAt')}: {formatTime(o.picked_up_at)}
          </li>
        )}
      </ol>

      {cancel.isError && (
        <div className="mt-3">
          <Alert tone="error">{errorMessage(cancel.error)}</Alert>
        </div>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        {o.can_cancel && (
          <Button
            variant="danger"
            disabled={cancel.isPending}
            onClick={() => {
              if (window.confirm(t('orders.cancelConfirm'))) cancel.mutate(o.id);
            }}
          >
            {t('orders.cancel')}
          </Button>
        )}
        <Button variant="secondary" disabled={repeat.isPending} onClick={() => repeat.run(o)}>
          {t('orders.repeat')}
        </Button>
      </div>
      {o.status === 'paid' && o.cancel_until && (
        <p className="mt-2 text-xs text-slate-500">
          {o.can_cancel
            ? t('orders.cancelUntil', { time: formatTime(o.cancel_until) })
            : t('orders.cancelClosed')}
        </p>
      )}
    </section>
  );
}
