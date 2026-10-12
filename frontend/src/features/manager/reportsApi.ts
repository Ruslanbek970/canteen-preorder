import { useQuery } from '@tanstack/react-query';

import { apiGet, qs } from '@/api/client';
import type { Dashboard, ReportName } from '@/api/types';
import { addDays, todayLocal } from '@/lib/format';

export interface Period {
  from: string;
  to: string;
}

/** The last `days` days up to today, inclusive. */
export function lastDays(days: number, today: string = todayLocal()): Period {
  return { from: addDays(today, -(days - 1)), to: today };
}

export function useDashboard() {
  return useQuery({
    queryKey: ['manager', 'dashboard'],
    queryFn: () => apiGet<Dashboard>('/manager/dashboard'),
    refetchInterval: 30_000,
  });
}

export function useReport<T>(name: ReportName, period: Period) {
  return useQuery({
    queryKey: ['manager', 'report', name, period.from, period.to],
    queryFn: () => apiGet<T>(`/manager/reports/${name}${qs({ from: period.from, to: period.to })}`),
  });
}

/** Downloads a report as CSV through the authenticated API client. */
export async function downloadCsv(name: ReportName, period: Period): Promise<void> {
  const text = await apiGet<string>(
    `/manager/reports/${name}.csv${qs({ from: period.from, to: period.to })}`,
  );
  // fetch() drops the BOM; Excel needs it to read Cyrillic as UTF-8.
  const blob = new Blob(['\ufeff', text], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${name}_${period.from}_${period.to}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
