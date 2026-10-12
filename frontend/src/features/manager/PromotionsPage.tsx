import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet, apiPost, qs } from '@/api/client';
import type { ManagerSlots, Promotion, PromotionStatus } from '@/api/types';
import {
  Alert,
  Badge,
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
import { formatClock, formatTime, todayLocal } from '@/lib/format';

import { ManagerShell } from './ManagerShell';

const KEY = ['manager', 'promotions'] as const;
const STATUS_TONE: Record<PromotionStatus, 'amber' | 'green' | 'gray' | 'red'> = {
  proposed: 'amber',
  active: 'green',
  rejected: 'red',
  expired: 'gray',
};

export function PromotionsPage() {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: KEY,
    queryFn: () => apiGet<Promotion[]>('/manager/promotions'),
    refetchInterval: 30_000,
  });
  return (
    <ManagerShell title={t('manager.promotions.title')}>
      <p className="mb-4 max-w-2xl text-sm text-slate-500">{t('manager.promotions.intro')}</p>
      {query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <div className="space-y-6">
            <PromotionGroup
              title={t('manager.promotions.proposed')}
              empty={t('manager.promotions.noProposed')}
              items={query.data.filter((p) => p.status === 'proposed')}
            />
            <PromotionGroup
              title={t('manager.promotions.current')}
              empty={t('manager.promotions.noCurrent')}
              items={query.data.filter((p) => p.status !== 'proposed')}
            />
          </div>
          <OffPeakForm />
        </div>
      )}
    </ManagerShell>
  );
}

function PromotionGroup({
  title,
  empty,
  items,
}: {
  title: string;
  empty: string;
  items: Promotion[];
}) {
  return (
    <section>
      <h2 className="mb-2 font-semibold">{title}</h2>
      {items.length === 0 ? (
        <EmptyState>{empty}</EmptyState>
      ) : (
        <ul className="space-y-2">
          {items.map((promo) => (
            <PromotionCard key={promo.id} promo={promo} />
          ))}
        </ul>
      )}
    </section>
  );
}

function PromotionCard({ promo }: { promo: Promotion }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const decide = useMutation({
    mutationFn: (action: 'approve' | 'reject') =>
      apiPost<Promotion>(`/manager/promotions/${promo.id}/${action}`),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: KEY });
      void client.invalidateQueries({ queryKey: ['manager', 'dashboard'] });
    },
  });
  const what =
    promo.type === 'off_peak'
      ? t('manager.promotions.slot', {
          from: formatClock(promo.slot_starts_at ?? ''),
          to: formatClock(promo.slot_ends_at ?? ''),
        })
      : (promo.dish_name ?? '');
  const detail =
    promo.type === 'off_peak'
      ? t('manager.promotions.slotLoad', {
          booked: promo.slot_booked ?? 0,
          capacity: promo.slot_capacity ?? 0,
        })
      : t('manager.promotions.left', {
          available: promo.available_portions ?? 0,
          planned: promo.planned_portions ?? 0,
        });
  return (
    <li>
      <Card className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xl font-semibold text-green-700 dark:text-green-400">
            −{promo.discount_percent}%
          </span>
          <span className="font-medium">{what}</span>
          <Badge tone={STATUS_TONE[promo.status]}>
            {t(`manager.promotions.status.${promo.status}`)}
          </Badge>
          <Badge tone="blue">{t(`manager.promotions.type.${promo.type}`)}</Badge>
        </div>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          {detail} · {t('manager.promotions.until', { time: formatTime(promo.valid_to) })}
          {promo.created_by_system && ` · ${t('manager.promotions.bySystem')}`}
        </p>
        {decide.isError && <Alert tone="error">{errorMessage(decide.error)}</Alert>}
        {promo.status === 'proposed' && (
          <div className="flex gap-2">
            <Button disabled={decide.isPending} onClick={() => decide.mutate('approve')}>
              {t('manager.promotions.approve')}
            </Button>
            <Button
              variant="secondary"
              disabled={decide.isPending}
              onClick={() => decide.mutate('reject')}
            >
              {t('manager.promotions.reject')}
            </Button>
          </div>
        )}
        {promo.status === 'proposed' && promo.type === 'leftover' && (
          <p className="text-xs text-slate-500">{t('manager.promotions.approveHint')}</p>
        )}
      </Card>
    </li>
  );
}

function OffPeakForm() {
  const { t } = useTranslation();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const date = todayLocal();
  const slots = useQuery({
    queryKey: ['manager', 'slots', date],
    queryFn: () => apiGet<ManagerSlots>(`/manager/slots${qs({ date })}`),
  });
  const [slotId, setSlotId] = useState('');
  const [percent, setPercent] = useState('20');
  const create = useMutation({
    mutationFn: () =>
      apiPost<Promotion>('/manager/promotions', {
        pickup_slot_id: Number(slotId),
        discount_percent: Number(percent),
      }),
    onSuccess: () => {
      setSlotId('');
      void client.invalidateQueries({ queryKey: KEY });
      void client.invalidateQueries({ queryKey: ['manager', 'slots'] });
    },
  });
  const open = (slots.data?.slots ?? []).filter((s) => !s.is_closed);
  return (
    <Card className="h-fit space-y-3">
      <h2 className="font-semibold">{t('manager.promotions.offPeakTitle')}</h2>
      <p className="text-sm text-slate-500">{t('manager.promotions.offPeakHint')}</p>
      {create.isError && <Alert tone="error">{errorMessage(create.error)}</Alert>}
      {create.isSuccess && <Alert tone="success">{t('manager.promotions.created')}</Alert>}
      {slots.isPending ? (
        <LoadingState />
      ) : slots.isError ? (
        <ErrorState error={slots.error} onRetry={() => void slots.refetch()} />
      ) : open.length === 0 ? (
        <EmptyState>{t('manager.promotions.noSlots')}</EmptyState>
      ) : (
        <>
          <Field label={t('manager.promotions.slotField')}>
            <Select value={slotId} onChange={(e) => setSlotId(e.target.value)}>
              <option value="">{t('manager.promotions.chooseSlot')}</option>
              {open.map((s) => (
                <option key={s.id} value={s.id}>
                  {formatClock(s.starts_at)}–{formatClock(s.ends_at)} ·{' '}
                  {t('manager.promotions.slotLoad', {
                    booked: s.booked_count,
                    capacity: s.capacity,
                  })}
                  {s.discount_percent ? ` · −${s.discount_percent}%` : ''}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t('manager.promotions.percent')} hint={t('manager.promotions.percentHint')}>
            <Input
              type="number"
              min={5}
              max={50}
              value={percent}
              onChange={(e) => setPercent(e.target.value)}
            />
          </Field>
          <Button
            className="w-full"
            disabled={!slotId || create.isPending}
            onClick={() => create.mutate()}
          >
            {t('manager.promotions.create')}
          </Button>
        </>
      )}
    </Card>
  );
}
