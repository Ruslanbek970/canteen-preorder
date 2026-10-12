import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiPost } from '@/api/client';
import type { AdminGroup } from '@/api/types';
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

import { ADMIN_KEY, useAdminGroups } from './api';
import { AdminShell } from './AdminShell';

export function AdminGroupsPage() {
  const { t } = useTranslation();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const groups = useAdminGroups();
  const [form, setForm] = useState({ code: '', faculty: '', study_year: '' });
  const create = useMutation({
    mutationFn: () =>
      apiPost<AdminGroup>('/admin/groups', {
        code: form.code,
        faculty: form.faculty || null,
        study_year: form.study_year ? Number(form.study_year) : null,
      }),
    onSuccess: () => {
      setForm({ code: '', faculty: '', study_year: '' });
      void client.invalidateQueries({ queryKey: [...ADMIN_KEY, 'groups'] });
      void client.invalidateQueries({ queryKey: ['groups'] });
    },
  });
  return (
    <AdminShell title={t('admin.groups.title')}>
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div>
          {groups.isPending ? (
            <LoadingState />
          ) : groups.isError ? (
            <ErrorState error={groups.error} onRetry={() => void groups.refetch()} />
          ) : groups.data.length === 0 ? (
            <EmptyState>{t('admin.groups.empty')}</EmptyState>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[420px] text-left text-sm">
                <thead className="text-slate-500">
                  <tr>
                    <th className="py-2 font-normal">{t('admin.groups.code')}</th>
                    <th className="font-normal">{t('admin.groups.faculty')}</th>
                    <th className="font-normal">{t('admin.groups.year')}</th>
                    <th className="text-right font-normal">{t('admin.groups.students')}</th>
                    <th className="text-right font-normal">{t('admin.groups.lessons')}</th>
                  </tr>
                </thead>
                <tbody>
                  {groups.data.map((g) => (
                    <tr key={g.id} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="py-2 font-medium">{g.code}</td>
                      <td>{g.faculty ?? '—'}</td>
                      <td>{g.study_year ?? '—'}</td>
                      <td className="text-right">{g.students}</td>
                      <td className="text-right">{g.lessons}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <Card className="h-fit space-y-3">
          <h2 className="font-semibold">{t('admin.groups.add')}</h2>
          {create.isError && <Alert>{errorMessage(create.error)}</Alert>}
          <Field label={t('admin.groups.code')} hint={t('admin.groups.codeHint')}>
            <Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
          </Field>
          <Field label={t('admin.groups.faculty')}>
            <Input
              value={form.faculty}
              onChange={(e) => setForm({ ...form, faculty: e.target.value })}
            />
          </Field>
          <Field label={t('admin.groups.year')}>
            <Input
              type="number"
              min={1}
              max={6}
              value={form.study_year}
              onChange={(e) => setForm({ ...form, study_year: e.target.value })}
            />
          </Field>
          <Button
            className="w-full"
            disabled={!form.code.trim() || create.isPending}
            onClick={() => create.mutate()}
          >
            {t('common.add')}
          </Button>
        </Card>
      </div>
    </AdminShell>
  );
}
