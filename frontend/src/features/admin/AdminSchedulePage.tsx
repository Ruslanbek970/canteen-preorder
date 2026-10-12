import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiPost } from '@/api/client';
import type { ScheduleImportResult } from '@/api/types';
import { Alert, Button, Card } from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';

import { ADMIN_KEY } from './api';
import { AdminShell } from './AdminShell';

const EXAMPLE = `group_code,day_of_week,starts_at,ends_at,building,subject
SE-2301,1,09:00,10:20,Главный корпус,Математика
SE-2301,1,10:30,11:50,Главный корпус,Программирование`;

function upload(file: File, dryRun: boolean) {
  const body = new FormData();
  body.append('file', file);
  return apiPost<ScheduleImportResult>(`/admin/schedule/import?dry_run=${dryRun}`, body);
}

export function AdminSchedulePage() {
  const { t } = useTranslation();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const [file, setFile] = useState<File | null>(null);
  const check = useMutation({ mutationFn: (f: File) => upload(f, true) });
  const run = useMutation({
    mutationFn: (f: File) => upload(f, false),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: [...ADMIN_KEY, 'groups'] });
      void client.invalidateQueries({ queryKey: ['slots'] });
    },
  });
  const result = run.data ?? check.data;
  const error = run.error ?? check.error;
  return (
    <AdminShell title={t('admin.schedule.title')}>
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <Card className="space-y-3">
          <p className="text-sm text-slate-600 dark:text-slate-300">{t('admin.schedule.intro')}</p>
          <input
            type="file"
            accept=".csv,text/csv"
            aria-label={t('admin.schedule.file')}
            className="block w-full text-sm"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              check.reset();
              run.reset();
            }}
          />
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              disabled={!file || check.isPending}
              onClick={() => file && check.mutate(file)}
            >
              {t('admin.schedule.check')}
            </Button>
            <Button
              disabled={
                !file ||
                run.isPending ||
                !check.data ||
                check.data.errors.length > 0 ||
                run.data?.imported === true
              }
              onClick={() => file && run.mutate(file)}
            >
              {t('admin.schedule.import')}
            </Button>
          </div>
          {error && <Alert>{errorMessage(error)}</Alert>}
          {result && <ImportResult result={result} />}
        </Card>
        <Card className="h-fit space-y-2 text-sm">
          <h2 className="font-semibold">{t('admin.schedule.format')}</h2>
          <p className="text-slate-500">{t('admin.schedule.formatHint')}</p>
          <pre className="overflow-x-auto rounded bg-slate-100 p-2 text-xs dark:bg-slate-800">
            {EXAMPLE}
          </pre>
        </Card>
      </div>
    </AdminShell>
  );
}

function ImportResult({ result }: { result: ScheduleImportResult }) {
  const { t } = useTranslation();
  if (result.errors.length > 0) {
    return (
      <div className="space-y-2">
        <Alert tone="error">{t('admin.schedule.hasErrors', { count: result.errors.length })}</Alert>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-slate-500">
              <tr>
                <th className="py-1 pr-3 font-normal">{t('admin.schedule.line')}</th>
                <th className="font-normal">{t('admin.schedule.problem')}</th>
              </tr>
            </thead>
            <tbody>
              {result.errors.map((e) => (
                <tr
                  key={`${e.line}-${e.code}`}
                  className="border-t border-slate-100 dark:border-slate-800"
                >
                  <td className="py-1 pr-3">{e.line || '—'}</td>
                  <td>{t(`admin.schedule.errors.${e.code}`, { defaultValue: e.message })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }
  const summary = t('admin.schedule.summary', {
    rows: result.rows,
    groups: result.groups.join(', '),
    deleted: result.deleted,
    created: result.created,
  });
  return result.imported ? (
    <Alert tone="success">
      {t('admin.schedule.done')} {summary}
    </Alert>
  ) : (
    <Alert tone="info">
      {t('admin.schedule.ready')} {summary}
    </Alert>
  );
}
