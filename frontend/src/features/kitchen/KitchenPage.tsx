import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import type { KitchenBoard, KitchenOrder } from '@/api/types';
import { Alert, Button, EmptyState, ErrorState, LoadingState } from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';
import { useMe } from '@/features/auth/useMe';
import { formatClock } from '@/lib/format';
import { useSocket } from '@/lib/socket';

import { KITCHEN_KEY, useBoard, usePrepSummary, useSetStatus, useStartSlot } from './api';
import { KitchenShell } from './KitchenShell';
import { playChime } from './sound';

type Column = 'paid' | 'cooking' | 'ready';
const COLUMNS: Column[] = ['paid', 'cooking', 'ready'];
const NEXT: Partial<Record<Column, 'cooking' | 'ready'>> = { paid: 'cooking', cooking: 'ready' };

export function KitchenPage() {
  const { t } = useTranslation();
  const me = useMe();
  const client = useQueryClient();
  const board = useBoard();
  const prep = usePrepSummary();
  const [sound, setSound] = useState(false);
  const [fresh, setFresh] = useState<number[]>([]);
  const canteenId = me.data?.canteen_id;

  useSocket(canteenId ? `/ws/kitchen/${canteenId}` : null, (message) => {
    if (!message.type.startsWith('order.')) return;
    void client.invalidateQueries({ queryKey: KITCHEN_KEY });
    if (message.type === 'order.paid') {
      setFresh((ids) => [...ids, Number(message.data.order_id)]);
      if (sound) playChime();
    }
  });

  return (
    <KitchenShell
      actions={
        <Button
          variant={sound ? 'secondary' : 'primary'}
          onClick={() => {
            if (!sound) playChime();
            setSound(!sound);
          }}
        >
          {sound ? t('kitchen.soundOff') : t('kitchen.soundOn')}
        </Button>
      }
    >
      <PrepPanel prep={prep} />
      {board.isPending ? (
        <LoadingState />
      ) : board.isError ? (
        <ErrorState error={board.error} onRetry={() => void board.refetch()} />
      ) : board.data.slots.every((s) => s.orders.length === 0) ? (
        <EmptyState>{t('kitchen.empty')}</EmptyState>
      ) : (
        <Board board={board.data} fresh={fresh} />
      )}
    </KitchenShell>
  );
}

function PrepPanel({ prep }: { prep: ReturnType<typeof usePrepSummary> }) {
  const { t } = useTranslation();
  if (prep.isPending || prep.isError || prep.data.slots.length === 0) return null;
  return (
    <section aria-label={t('kitchen.prepTitle')} className="mb-4 grid gap-2 md:grid-cols-3">
      {prep.data.slots.map((slot) => (
        <div
          key={slot.slot_id}
          className="rounded-xl border border-amber-300 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950"
        >
          <div className="font-semibold">
            {t('kitchen.prepFor', { time: formatClock(slot.starts_at), count: slot.orders })}
          </div>
          <div>{slot.items.map((i) => `${i.name} × ${i.quantity}`).join(', ')}</div>
        </div>
      ))}
    </section>
  );
}

function Board({ board, fresh }: { board: KitchenBoard; fresh: number[] }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const setStatus = useSetStatus();
  const startSlot = useStartSlot();
  const errorMessage = useErrorMessage();
  const error = setStatus.error ?? startSlot.error;

  return (
    <>
      {error && (
        <div className="mb-3">
          <Alert tone="error">{errorMessage(error)}</Alert>
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-3">
        {COLUMNS.map((column) => (
          <section key={column} aria-label={t(`kitchen.columns.${column}`)}>
            <h2 className="mb-2 text-xl font-semibold">
              {t(`kitchen.columns.${column}`)} · {board.counts[column]}
            </h2>
            <div className="space-y-3">
              {board.slots.map((slot) => {
                const orders = slot.orders.filter((o) => o.status === column);
                if (orders.length === 0) return null;
                return (
                  <div key={slot.slot_id ?? 'none'} className="space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="font-semibold text-slate-600 dark:text-slate-300">
                        {slot.starts_at
                          ? `${formatClock(slot.starts_at)}–${formatClock(slot.ends_at ?? '')}`
                          : t('kitchen.noSlot')}
                      </h3>
                      {column === 'paid' && slot.slot_id !== null && (
                        <Button
                          variant="secondary"
                          disabled={startSlot.isPending}
                          onClick={() =>
                            startSlot.mutate(slot.slot_id as number, {
                              onSuccess: (r) =>
                                r.order_ids.length > 0 &&
                                navigate(`/kitchen/labels?ids=${r.order_ids.join(',')}`),
                            })
                          }
                        >
                          {t('kitchen.startSlot')}
                        </Button>
                      )}
                    </div>
                    {orders.map((order) => (
                      <OrderCard
                        key={order.id}
                        order={order}
                        isNew={fresh.includes(order.id)}
                        busy={setStatus.isPending}
                        onNext={() => {
                          const next = NEXT[column];
                          if (next) setStatus.mutate({ id: order.id, status: next });
                        }}
                      />
                    ))}
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}

function OrderCard({
  order,
  isNew,
  busy,
  onNext,
}: {
  order: KitchenOrder;
  isNew: boolean;
  busy: boolean;
  onNext: () => void;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const action =
    order.status === 'paid'
      ? t('kitchen.toCooking')
      : order.status === 'cooking'
        ? t('kitchen.toReady')
        : null;
  return (
    <article
      aria-label={order.order_number}
      className={`rounded-xl border bg-white p-3 shadow-sm dark:bg-slate-900 ${
        isNew && order.status === 'paid'
          ? 'border-green-500 ring-2 ring-green-300'
          : 'border-slate-200 dark:border-slate-800'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-3xl font-bold">{order.order_number}</span>
        {order.pickup_shelf !== null && (
          <span className="rounded-lg bg-green-600 px-2 py-1 font-semibold text-white">
            {t('kitchen.shelf', { shelf: order.pickup_shelf })}
          </span>
        )}
      </div>
      <ul className="mt-1">
        {order.items.map((i) => (
          <li key={i.menu_item_id}>
            {i.name} × <b>{i.quantity}</b>
          </li>
        ))}
      </ul>
      {order.allergy_flag && (
        <p className="mt-2 rounded bg-red-600 px-2 py-1 font-bold text-white">
          {order.allergy_flag}
        </p>
      )}
      <div className="mt-3 flex gap-2">
        {action && (
          <Button className="flex-1" disabled={busy} onClick={onNext}>
            {action}
          </Button>
        )}
        <Button variant="secondary" onClick={() => navigate(`/kitchen/labels?ids=${order.id}`)}>
          {t('kitchen.label')}
        </Button>
      </div>
    </article>
  );
}
