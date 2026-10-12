import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Button, Card, EmptyState, ErrorState, LoadingState, PageTitle } from '@/components/ui';
import { formatClock, formatDay, formatPrice } from '@/lib/format';

import { useOrders } from './api';
import { StatusBadge } from './StatusBadge';
import { useRepeat } from './useRepeat';

export function OrdersPage() {
  const { t } = useTranslation();
  const orders = useOrders();
  const repeat = useRepeat();

  return (
    <section className="p-4">
      <PageTitle>{t('pages.orders')}</PageTitle>
      {orders.isPending ? (
        <LoadingState />
      ) : orders.isError ? (
        <ErrorState error={orders.error} onRetry={() => void orders.refetch()} />
      ) : orders.data.items.length === 0 ? (
        <EmptyState>
          {t('orders.empty')}{' '}
          <Link to="/menu" className="text-green-700 underline dark:text-green-400">
            {t('cart.toMenu')}
          </Link>
        </EmptyState>
      ) : (
        <ul className="space-y-3">
          {orders.data.items.map((order) => (
            <li key={order.id}>
              <Card>
                <div className="flex items-start justify-between gap-2">
                  <Link to={`/orders/${order.id}`} className="min-w-0 hover:underline">
                    <div className="text-lg font-semibold">{order.order_number}</div>
                    <div className="text-sm text-slate-500">
                      {formatDay(order.service_date)}
                      {order.pickup_slot
                        ? ` · ${formatClock(order.pickup_slot.starts_at)}–${formatClock(order.pickup_slot.ends_at)}`
                        : ''}
                    </div>
                  </Link>
                  <div className="text-right">
                    <StatusBadge status={order.status} />
                    <div className="mt-1 font-semibold">{formatPrice(order.total)}</div>
                  </div>
                </div>
                <p className="mt-2 truncate text-sm text-slate-600 dark:text-slate-300">
                  {order.items.map((i) => `${i.name_ru} × ${i.quantity}`).join(', ')}
                </p>
                <div className="mt-2 flex justify-end gap-2">
                  {order.review_until && order.items.some((i) => i.my_rating === null) && (
                    <Link
                      to={`/orders/${order.id}`}
                      className="inline-flex min-h-[44px] items-center rounded-lg px-4 font-medium text-green-700 hover:bg-green-50"
                    >
                      {t('reviews.rate')}
                    </Link>
                  )}
                  <Button
                    variant="secondary"
                    disabled={repeat.isPending}
                    onClick={() => repeat.run(order)}
                  >
                    {t('orders.repeat')}
                  </Button>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
