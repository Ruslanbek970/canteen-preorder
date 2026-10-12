import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiPost } from '@/api/client';
import type { MenuItem, PosReceipt } from '@/api/types';
import { Alert, Button, Card, EmptyState, ErrorState, LoadingState } from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';
import { useMe } from '@/features/auth/useMe';
import { useMenu } from '@/features/menu/useMenu';
import { PickupShell } from '@/features/pickup/PickupShell';
import { formatPrice } from '@/lib/format';

type Method = 'cash' | 'kaspi_qr';

export function PosPage() {
  const { t } = useTranslation();
  const me = useMe();
  const menu = useMenu(me.data?.canteen_id);
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const [cart, setCart] = useState<Record<number, number>>({});
  const [method, setMethod] = useState<Method>('cash');
  const [receipt, setReceipt] = useState<PosReceipt | null>(null);
  const sell = useMutation({
    mutationFn: () =>
      apiPost<PosReceipt>('/pos/sales', {
        items: Object.entries(cart).map(([id, quantity]) => ({
          menu_item_id: Number(id),
          quantity,
        })),
        method,
      }),
    onSuccess: (r) => {
      setReceipt(r);
      setCart({});
    },
    onSettled: () => void client.invalidateQueries({ queryKey: ['menu'] }),
  });

  const items = menu.data?.items ?? [];
  const byId = new Map(items.map((i) => [i.id, i]));
  const lines = Object.entries(cart)
    .map(([id, q]) => ({ item: byId.get(Number(id)), quantity: q }))
    .filter((l): l is { item: MenuItem; quantity: number } => Boolean(l.item));
  const total = lines.reduce((sum, l) => sum + Number(l.item.price_now) * l.quantity, 0);
  const add = (item: MenuItem, delta: number) => {
    setReceipt(null);
    setCart((c) => {
      const next = Math.max(0, Math.min((c[item.id] ?? 0) + delta, 10, item.available_portions));
      const copy = { ...c };
      if (next === 0) delete copy[item.id];
      else copy[item.id] = next;
      return copy;
    });
  };

  return (
    <PickupShell>
      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <div>
          {menu.isPending ? (
            <LoadingState />
          ) : menu.isError ? (
            <ErrorState error={menu.error} onRetry={() => void menu.refetch()} />
          ) : items.length === 0 ? (
            <EmptyState>{t('menu.empty')}</EmptyState>
          ) : (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  disabled={item.available_portions === 0}
                  onClick={() => add(item, 1)}
                  className="flex min-h-[96px] flex-col justify-between rounded-xl border border-slate-200 bg-white p-3 text-left disabled:opacity-40 dark:border-slate-700 dark:bg-slate-900"
                >
                  <span className="font-semibold leading-tight">{item.name_ru}</span>
                  <span className="flex justify-between text-base">
                    <span>{formatPrice(item.price_now)}</span>
                    <span className="text-slate-500">
                      {t('menu.left', { count: item.available_portions })}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        <Card>
          <h2 className="mb-2 text-xl font-semibold">{t('pos.cart')}</h2>
          {lines.length === 0 ? (
            <p className="text-slate-500">{t('pos.empty')}</p>
          ) : (
            <ul className="mb-3 divide-y divide-slate-100 dark:divide-slate-800">
              {lines.map(({ item, quantity }) => (
                <li key={item.id} className="flex items-center justify-between gap-2 py-2">
                  <span className="min-w-0 truncate">{item.name_ru}</span>
                  <span className="flex items-center gap-2">
                    <Button
                      variant="secondary"
                      aria-label={t('cart.decrease')}
                      onClick={() => add(item, -1)}
                    >
                      −
                    </Button>
                    <b>{quantity}</b>
                    <Button
                      variant="secondary"
                      aria-label={t('cart.increase')}
                      onClick={() => add(item, 1)}
                    >
                      +
                    </Button>
                  </span>
                </li>
              ))}
            </ul>
          )}
          <fieldset className="mb-3">
            <legend className="mb-1 text-sm text-slate-500">{t('pos.method')}</legend>
            <div className="flex gap-2">
              {(['cash', 'kaspi_qr'] as Method[]).map((m) => (
                <label
                  key={m}
                  className={`flex-1 cursor-pointer rounded-lg border px-3 py-2 text-center ${
                    method === m
                      ? 'border-green-600 bg-green-50 dark:bg-green-950'
                      : 'border-slate-300 dark:border-slate-700'
                  }`}
                >
                  <input
                    type="radio"
                    name="method"
                    className="sr-only"
                    checked={method === m}
                    onChange={() => setMethod(m)}
                  />
                  {t(`pos.methods.${m}`)}
                </label>
              ))}
            </div>
          </fieldset>
          <div className="mb-3 flex justify-between text-2xl font-bold">
            <span>{t('cart.total')}</span>
            <span data-testid="pos-total">{formatPrice(total)}</span>
          </div>
          {sell.isError && (
            <div className="mb-2">
              <Alert tone="error">{errorMessage(sell.error)}</Alert>
            </div>
          )}
          <Button
            className="w-full text-xl"
            disabled={lines.length === 0 || sell.isPending}
            onClick={() => sell.mutate()}
          >
            {t('pos.sell')}
          </Button>
          {receipt && (
            <div className="mt-3">
              <Alert tone="success">
                {t('pos.sold', { number: receipt.order_number, total: formatPrice(receipt.total) })}
                {receipt.fiscal_receipt_number &&
                  ` · ${t('pos.receipt', { number: receipt.fiscal_receipt_number })}`}
              </Alert>
            </div>
          )}
        </Card>
      </div>
    </PickupShell>
  );
}
