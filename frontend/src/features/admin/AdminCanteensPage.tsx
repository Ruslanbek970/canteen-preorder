import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiPatch, apiPost } from '@/api/client';
import type { AdminCanteen } from '@/api/types';
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
import { formatClock } from '@/lib/format';

import { ADMIN_KEY, useAdminCanteens, useBuildings } from './api';
import { AdminShell } from './AdminShell';

type Form = Record<
  | 'name'
  | 'building_id'
  | 'slug'
  | 'opens_at'
  | 'closes_at'
  | 'default_slot_minutes'
  | 'default_slot_capacity'
  | 'pickup_shelves_count'
  | 'order_cutoff_minutes',
  string
> & { is_active: boolean };

const EMPTY: Form = {
  name: '',
  building_id: '',
  slug: '',
  opens_at: '09:00',
  closes_at: '17:00',
  default_slot_minutes: '10',
  default_slot_capacity: '30',
  pickup_shelves_count: '10',
  order_cutoff_minutes: '15',
  is_active: true,
};

const toForm = (c: AdminCanteen): Form => ({
  name: c.name,
  building_id: String(c.building_id),
  slug: c.slug ?? '',
  opens_at: c.opens_at.slice(0, 5),
  closes_at: c.closes_at.slice(0, 5),
  default_slot_minutes: String(c.default_slot_minutes),
  default_slot_capacity: String(c.default_slot_capacity),
  pickup_shelves_count: String(c.pickup_shelves_count),
  order_cutoff_minutes: String(c.order_cutoff_minutes),
  is_active: c.is_active,
});

const toBody = (f: Form) => ({
  name: f.name,
  building_id: Number(f.building_id),
  slug: f.slug || null,
  opens_at: f.opens_at,
  closes_at: f.closes_at,
  default_slot_minutes: Number(f.default_slot_minutes),
  default_slot_capacity: Number(f.default_slot_capacity),
  pickup_shelves_count: Number(f.pickup_shelves_count),
  order_cutoff_minutes: Number(f.order_cutoff_minutes),
  is_active: f.is_active,
});

export function AdminCanteensPage() {
  const { t } = useTranslation();
  const canteens = useAdminCanteens();
  const [creating, setCreating] = useState(false);
  return (
    <AdminShell title={t('admin.canteens.title')}>
      <Button variant="secondary" className="mb-4" onClick={() => setCreating((v) => !v)}>
        {t('admin.canteens.add')}
      </Button>
      {creating && <CanteenForm onDone={() => setCreating(false)} />}
      {canteens.isPending ? (
        <LoadingState />
      ) : canteens.isError ? (
        <ErrorState error={canteens.error} onRetry={() => void canteens.refetch()} />
      ) : canteens.data.length === 0 ? (
        <EmptyState>{t('admin.canteens.empty')}</EmptyState>
      ) : (
        <ul className="space-y-3">
          {canteens.data.map((c) => (
            <CanteenRow key={c.id} canteen={c} />
          ))}
        </ul>
      )}
    </AdminShell>
  );
}

function CanteenRow({ canteen }: { canteen: AdminCanteen }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <li>
      <Card className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="font-medium">
              {canteen.name}{' '}
              {!canteen.is_active && <Badge tone="gray">{t('admin.canteens.inactive')}</Badge>}
            </p>
            <p className="text-sm text-slate-500">
              {formatClock(canteen.opens_at)}–{formatClock(canteen.closes_at)} ·{' '}
              {t('admin.canteens.slotSummary', {
                minutes: canteen.default_slot_minutes,
                capacity: canteen.default_slot_capacity,
              })}
              {canteen.slug ? ` · /c/${canteen.slug}` : ''}
            </p>
          </div>
          <Button variant="ghost" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
            {open ? t('common.close') : t('common.edit')}
          </Button>
        </div>
        {open && <CanteenForm canteen={canteen} onDone={() => setOpen(false)} />}
      </Card>
    </li>
  );
}

function CanteenForm({ canteen, onDone }: { canteen?: AdminCanteen; onDone: () => void }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const buildings = useBuildings();
  const [form, setForm] = useState<Form>(canteen ? toForm(canteen) : EMPTY);
  const save = useMutation({
    mutationFn: () =>
      canteen
        ? apiPatch<AdminCanteen>(`/admin/canteens/${canteen.id}`, toBody(form))
        : apiPost<AdminCanteen>('/admin/canteens', toBody(form)),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: [...ADMIN_KEY, 'canteens'] });
      void client.invalidateQueries({ queryKey: ['canteens'] });
      onDone();
    },
  });
  const text = (key: keyof Form, type = 'text') => (
    <Input
      type={type}
      value={String(form[key])}
      onChange={(e) => setForm({ ...form, [key]: e.target.value })}
    />
  );
  return (
    <div
      className={`grid gap-3 sm:grid-cols-2 lg:grid-cols-4 ${canteen ? 'border-t border-slate-200 pt-3 dark:border-slate-800' : 'mb-4'}`}
    >
      {save.isError && (
        <div className="sm:col-span-2 lg:col-span-4">
          <Alert>{errorMessage(save.error)}</Alert>
        </div>
      )}
      <Field label={t('admin.canteens.name')}>{text('name')}</Field>
      <Field label={t('admin.canteens.building')}>
        <Select
          value={form.building_id}
          onChange={(e) => setForm({ ...form, building_id: e.target.value })}
        >
          <option value="">—</option>
          {buildings.data?.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </Select>
      </Field>
      <Field label={t('admin.canteens.slug')} hint={t('admin.canteens.slugHint')}>
        {text('slug')}
      </Field>
      <Field label={t('admin.canteens.opens')}>{text('opens_at', 'time')}</Field>
      <Field label={t('admin.canteens.closes')}>{text('closes_at', 'time')}</Field>
      <Field label={t('admin.canteens.slotMinutes')}>
        {text('default_slot_minutes', 'number')}
      </Field>
      <Field label={t('admin.canteens.slotCapacity')}>
        {text('default_slot_capacity', 'number')}
      </Field>
      <Field label={t('admin.canteens.shelves')}>{text('pickup_shelves_count', 'number')}</Field>
      <Field label={t('admin.canteens.cutoff')} hint={t('admin.canteens.cutoffHint')}>
        {text('order_cutoff_minutes', 'number')}
      </Field>
      <label className="flex items-center gap-2 self-center">
        <input
          type="checkbox"
          className="h-5 w-5"
          checked={form.is_active}
          onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
        />
        {t('admin.canteens.active')}
      </label>
      <div className="sm:col-span-2 lg:col-span-4">
        <Button
          disabled={save.isPending || !form.name || !form.building_id}
          onClick={() => save.mutate()}
        >
          {canteen ? t('common.save') : t('admin.canteens.create')}
        </Button>
      </div>
    </div>
  );
}
