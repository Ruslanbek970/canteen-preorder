import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet, apiPatch, apiPost, qs } from '@/api/client';
import type { ManagerSlots, Slot } from '@/api/types';
import {
  Alert,
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingState,
} from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';
import { formatClock, todayLocal } from '@/lib/format';

import { ManagerShell } from './ManagerShell';

export function ManagerSlotsPage() {
  const { t } = useTranslation();
  const [date, setDate] = useState(todayLocal);
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const key = ['manager', 'slots', date];
  const slots = useQuery({
    queryKey: key,
    queryFn: () => apiGet<ManagerSlots>(`/manager/slots${qs({ date })}`),
  });
  const generate = useMutation({
    mutationFn: () => apiPost<ManagerSlots>(`/manager/slots/generate${qs({ date })}`),
    onSuccess: (data) => client.setQueryData(key, data),
  });

  return (
    <ManagerShell
      title={t('manager.slots.title')}
      actions={
        <Field label={t('manager.menu.date')}>
          <Input
            type="date"
            value={date}
            onChange={(e) => e.target.value && setDate(e.target.value)}
          />
        </Field>
      }
    >
      {generate.isError && <Alert tone="error">{errorMessage(generate.error)}</Alert>}
      {slots.isPending ? (
        <LoadingState />
      ) : slots.isError ? (
        <ErrorState error={slots.error} onRetry={() => void slots.refetch()} />
      ) : slots.data.slots.length === 0 ? (
        <EmptyState>
          <p className="mb-3">{t('manager.slots.empty')}</p>
          <Button disabled={generate.isPending} onClick={() => generate.mutate()}>
            {t('manager.slots.generate')}
          </Button>
        </EmptyState>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-sm">
            <thead className="text-slate-500">
              <tr>
                <th className="py-2">{t('manager.slots.time')}</th>
                <th>{t('manager.slots.booked')}</th>
                <th>{t('manager.slots.capacity')}</th>
                <th>{t('manager.slots.state')}</th>
              </tr>
            </thead>
            <tbody>
              {slots.data.slots.map((slot) => (
                <SlotRow
                  key={`${slot.id}-${slot.capacity}-${slot.is_closed}`}
                  slot={slot}
                  date={date}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </ManagerShell>
  );
}

function SlotRow({ slot, date }: { slot: Slot; date: string }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const [capacity, setCapacity] = useState(String(slot.capacity));
  const patch = useMutation({
    mutationFn: (body: { capacity?: number; is_closed?: boolean }) =>
      apiPatch<Slot>(`/manager/slots/${slot.id}`, body),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['manager', 'slots', date] }),
  });
  const changed = Number(capacity) !== slot.capacity && Number(capacity) > 0;
  const fill = slot.capacity ? slot.booked_count / slot.capacity : 0;

  return (
    <tr className="border-t border-slate-100 dark:border-slate-800">
      <td className="py-2 font-medium">
        {formatClock(slot.starts_at)}–{formatClock(slot.ends_at)}
        {slot.discount_percent ? (
          <span className="ml-2">
            <Badge tone="red">−{slot.discount_percent}%</Badge>
          </span>
        ) : null}
      </td>
      <td>
        <span className={fill >= 1 ? 'font-semibold text-red-600' : ''}>
          {slot.booked_count} / {slot.capacity}
        </span>
      </td>
      <td>
        <div className="flex items-center gap-2">
          <Input
            type="number"
            min={1}
            className="w-20"
            aria-label={`${t('manager.slots.capacity')} ${formatClock(slot.starts_at)}`}
            value={capacity}
            onChange={(e) => setCapacity(e.target.value)}
          />
          {changed && (
            <Button
              variant="secondary"
              disabled={patch.isPending}
              onClick={() => patch.mutate({ capacity: Number(capacity) })}
            >
              {t('common.save')}
            </Button>
          )}
        </div>
        {patch.isError && <p className="mt-1 text-xs text-red-600">{errorMessage(patch.error)}</p>}
      </td>
      <td>
        <Button
          variant={slot.is_closed ? 'primary' : 'ghost'}
          disabled={patch.isPending}
          onClick={() => patch.mutate({ is_closed: !slot.is_closed })}
        >
          {slot.is_closed ? t('manager.slots.open') : t('manager.slots.close')}
        </Button>
      </td>
    </tr>
  );
}
