import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet, apiPost } from '@/api/client';
import type { PickupOrder } from '@/api/types';
import { Alert, Button, Card, Input } from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';
import { formatClock, formatPrice } from '@/lib/format';

import { PickupShell } from './PickupShell';
import { QrScanner } from './QrScanner';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function PickupPage() {
  const { t } = useTranslation();
  const errorMessage = useErrorMessage();
  const [number, setNumber] = useState('');
  const [camera, setCamera] = useState(false);
  const [order, setOrder] = useState<PickupOrder | null>(null);
  const find = useMutation({
    mutationFn: (query: string) =>
      apiGet<PickupOrder>(
        UUID.test(query)
          ? `/pickup/scan/${query}`
          : `/pickup/by-number/${encodeURIComponent(query)}`,
      ),
    onSuccess: setOrder,
    onError: () => setOrder(null),
  });
  const handOver = useMutation({
    mutationFn: (id: number) => apiPost<PickupOrder>(`/pickup/orders/${id}/confirm`),
    onSuccess: setOrder,
  });

  return (
    <PickupShell>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (number.trim()) find.mutate(number.trim());
            }}
          >
            <Input
              aria-label={t('pickup.number')}
              placeholder={t('pickup.numberPlaceholder')}
              className="text-2xl"
              value={number}
              onChange={(e) => setNumber(e.target.value)}
              autoFocus
            />
            <Button type="submit" disabled={find.isPending}>
              {t('pickup.find')}
            </Button>
          </form>
          <Button variant="secondary" className="w-full" onClick={() => setCamera(!camera)}>
            {camera ? t('pickup.cameraOff') : t('pickup.cameraOn')}
          </Button>
          {camera && (
            <QrScanner
              paused={find.isPending}
              onScan={(text) => {
                handOver.reset();
                find.mutate(text);
              }}
            />
          )}
        </div>

        <div>
          {find.isError && <Alert tone="error">{errorMessage(find.error)}</Alert>}
          {order && (
            <OrderCard
              order={order}
              busy={handOver.isPending}
              error={handOver.isError ? errorMessage(handOver.error) : null}
              onHandOver={() => handOver.mutate(order.id)}
            />
          )}
          {!order && !find.isError && <p className="text-slate-500">{t('pickup.hint')}</p>}
        </div>
      </div>
    </PickupShell>
  );
}

function OrderCard({
  order,
  busy,
  error,
  onHandOver,
}: {
  order: PickupOrder;
  busy: boolean;
  error: string | null;
  onHandOver: () => void;
}) {
  const { t } = useTranslation();
  const notReady = order.status === 'paid' || order.status === 'cooking';
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-5xl font-bold">{order.order_number}</div>
          <div className="text-slate-500">
            {order.customer_name}
            {order.starts_at &&
              ` · ${formatClock(order.starts_at)}–${formatClock(order.ends_at ?? '')}`}
          </div>
        </div>
        {order.pickup_shelf !== null && (
          <div className="rounded-xl bg-green-600 px-4 py-2 text-center text-white">
            <div className="text-sm">{t('pickup.shelf')}</div>
            <div className="text-5xl font-bold" data-testid="shelf">
              {order.pickup_shelf}
            </div>
          </div>
        )}
      </div>
      <ul className="mt-3 text-xl">
        {order.items.map((i) => (
          <li key={i.menu_item_id}>
            {i.name} × <b>{i.quantity}</b>
          </li>
        ))}
      </ul>
      <p className="mt-1 text-slate-500">{formatPrice(order.total)}</p>
      {order.allergy_flag && (
        <p className="mt-3 rounded bg-red-600 px-3 py-2 text-xl font-bold text-white">
          {order.allergy_flag}
        </p>
      )}
      <div className="mt-4">
        {order.status === 'ready' ? (
          <Button className="w-full text-2xl" disabled={busy} onClick={onHandOver}>
            {t('pickup.handOver')}
          </Button>
        ) : (
          <p
            className={`rounded-xl p-4 text-center text-3xl font-bold ${
              notReady
                ? 'bg-amber-100 text-amber-900 dark:bg-amber-900 dark:text-amber-100'
                : order.status === 'picked_up'
                  ? 'bg-slate-100 dark:bg-slate-800'
                  : 'bg-red-100 text-red-900 dark:bg-red-900 dark:text-red-100'
            }`}
            role="status"
          >
            {notReady ? t('pickup.stillCooking') : t(`orders.status.${order.status}`)}
          </p>
        )}
        {error && (
          <div className="mt-2">
            <Alert tone="error">{error}</Alert>
          </div>
        )}
      </div>
    </Card>
  );
}
