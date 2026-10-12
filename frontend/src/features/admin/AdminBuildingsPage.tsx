import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiPost } from '@/api/client';
import type { Building } from '@/api/types';
import {
  Alert,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingState,
} from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';

import { ADMIN_KEY, useBuildings } from './api';
import { AdminShell } from './AdminShell';

export function AdminBuildingsPage() {
  const { t } = useTranslation();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const buildings = useBuildings();
  const [form, setForm] = useState({ name: '', address: '' });
  const create = useMutation({
    mutationFn: () =>
      apiPost<Building>('/admin/buildings', { name: form.name, address: form.address || null }),
    onSuccess: () => {
      setForm({ name: '', address: '' });
      void client.invalidateQueries({ queryKey: [...ADMIN_KEY, 'buildings'] });
    },
  });
  return (
    <AdminShell title={t('admin.buildings.title')}>
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div>
          {buildings.isPending ? (
            <LoadingState />
          ) : buildings.isError ? (
            <ErrorState error={buildings.error} onRetry={() => void buildings.refetch()} />
          ) : buildings.data.length === 0 ? (
            <EmptyState>{t('admin.buildings.empty')}</EmptyState>
          ) : (
            <ul className="space-y-2">
              {buildings.data.map((b) => (
                <li key={b.id}>
                  <Card>
                    <p className="font-medium">{b.name}</p>
                    {b.address && <p className="text-sm text-slate-500">{b.address}</p>}
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </div>
        <Card className="h-fit space-y-3">
          <h2 className="font-semibold">{t('admin.buildings.add')}</h2>
          {create.isError && <Alert>{errorMessage(create.error)}</Alert>}
          <Field label={t('admin.buildings.name')}>
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <Field label={t('admin.buildings.address')}>
            <Input
              value={form.address}
              onChange={(e) => setForm({ ...form, address: e.target.value })}
            />
          </Field>
          <Button
            className="w-full"
            disabled={!form.name.trim() || create.isPending}
            onClick={() => create.mutate()}
          >
            {t('common.add')}
          </Button>
        </Card>
      </div>
    </AdminShell>
  );
}
