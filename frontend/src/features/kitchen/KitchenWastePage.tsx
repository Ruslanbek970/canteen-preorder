import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import type { CloseDayResult } from '@/api/types';
import {
  Alert,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingState,
  Select,
} from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';
import { useMe } from '@/features/auth/useMe';
import { useMenu } from '@/features/menu/useMenu';
import { formatTime } from '@/lib/format';

import { useCloseDay, useRecordWaste, useWaste } from './api';
import { KitchenShell } from './KitchenShell';

const REASONS = ['damaged', 'expired', 'other'] as const;

export function KitchenWastePage() {
  const { t } = useTranslation();
  const me = useMe();
  const menu = useMenu(me.data?.canteen_id);
  const waste = useWaste();
  const record = useRecordWaste();
  const closeDay = useCloseDay();
  const errorMessage = useErrorMessage();
  const [menuItemId, setMenuItemId] = useState('');
  const [portions, setPortions] = useState('1');
  const [reason, setReason] = useState<(typeof REASONS)[number]>('damaged');
  const [closed, setClosed] = useState<CloseDayResult | null>(null);
  const items = menu.data?.items ?? [];

  return (
    <KitchenShell>
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <h2 className="mb-3 text-xl font-semibold">{t('kitchen.waste.title')}</h2>
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              record.mutate(
                { menu_item_id: Number(menuItemId), portions: Number(portions), reason },
                { onSuccess: () => setPortions('1') },
              );
            }}
          >
            <Field label={t('kitchen.waste.dish')}>
              <Select value={menuItemId} onChange={(e) => setMenuItemId(e.target.value)} required>
                <option value="">—</option>
                {items.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.name_ru} ({t('menu.left', { count: i.available_portions })})
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t('kitchen.waste.portions')}>
              <Input
                type="number"
                min={1}
                value={portions}
                onChange={(e) => setPortions(e.target.value)}
                required
              />
            </Field>
            <Field label={t('kitchen.waste.reason')}>
              <Select
                value={reason}
                onChange={(e) => setReason(e.target.value as (typeof REASONS)[number])}
              >
                {REASONS.map((r) => (
                  <option key={r} value={r}>
                    {t(`kitchen.waste.reasons.${r}`)}
                  </option>
                ))}
              </Select>
            </Field>
            {record.isError && <Alert tone="error">{errorMessage(record.error)}</Alert>}
            <Button type="submit" disabled={record.isPending || !menuItemId}>
              {t('kitchen.waste.submit')}
            </Button>
          </form>
        </Card>

        <Card>
          <h2 className="mb-2 text-xl font-semibold">{t('kitchen.closeDay.title')}</h2>
          <p className="mb-3 text-base text-slate-600 dark:text-slate-300">
            {t('kitchen.closeDay.hint')}
          </p>
          <Button
            variant="danger"
            disabled={closeDay.isPending}
            onClick={() => {
              if (window.confirm(t('kitchen.closeDay.confirm')))
                closeDay.mutate(undefined, { onSuccess: setClosed });
            }}
          >
            {t('kitchen.closeDay.button')}
          </Button>
          {closeDay.isError && (
            <div className="mt-3">
              <Alert tone="error">{errorMessage(closeDay.error)}</Alert>
            </div>
          )}
          {closed && (
            <div className="mt-3">
              <Alert tone="success">
                {closed.written_off.length === 0
                  ? t('kitchen.closeDay.nothing')
                  : t('kitchen.closeDay.done', {
                      list: closed.written_off
                        .map((w) => `${w.dish_name} × ${w.portions}`)
                        .join(', '),
                    })}
                {closed.kept.length > 0 &&
                  ` ${t('kitchen.closeDay.kept', {
                    list: closed.kept.map((k) => `${k.name} × ${k.quantity}`).join(', '),
                  })}`}
              </Alert>
            </div>
          )}
        </Card>
      </div>

      <h2 className="mb-2 mt-6 text-xl font-semibold">{t('kitchen.waste.today')}</h2>
      {waste.isPending ? (
        <LoadingState />
      ) : waste.isError ? (
        <ErrorState error={waste.error} onRetry={() => void waste.refetch()} />
      ) : waste.data.length === 0 ? (
        <EmptyState>{t('kitchen.waste.empty')}</EmptyState>
      ) : (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900">
          {waste.data.map((w) => (
            <li key={w.id} className="flex justify-between gap-2 px-4 py-2">
              <span>
                {w.dish_name} × {w.portions}
              </span>
              <span className="text-slate-500">
                {t(`kitchen.waste.reasons.${w.reason}`)} · {formatTime(w.recorded_at)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </KitchenShell>
  );
}
