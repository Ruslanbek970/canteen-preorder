import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import type { Dashboard } from '@/api/types';
import { Card, EmptyState, ErrorState, LoadingState } from '@/components/ui';
import { formatClock, formatDay, formatPrice } from '@/lib/format';

import { ManagerShell } from './ManagerShell';
import { useDashboard } from './reportsApi';

export function ManagerDashboardPage() {
  const { t } = useTranslation();
  const dashboard = useDashboard();
  return (
    <ManagerShell
      title={t('manager.dashboard.title')}
      actions={
        <Link to="/manager/reports" className="text-sm text-brand-700 underline">
          {t('manager.dashboard.toReports')}
        </Link>
      }
    >
      {dashboard.isPending ? (
        <LoadingState />
      ) : dashboard.isError ? (
        <ErrorState error={dashboard.error} onRetry={() => void dashboard.refetch()} />
      ) : (
        <DashboardView data={dashboard.data} />
      )}
    </ManagerShell>
  );
}

function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <Card>
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </Card>
  );
}

function DashboardView({ data }: { data: Dashboard }) {
  const { t } = useTranslation();
  const active =
    data.orders_by_status.paid + data.orders_by_status.cooking + data.orders_by_status.ready;
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">
        {t('manager.dashboard.today', { date: formatDay(data.date) })}
      </p>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Stat
          label={t('manager.dashboard.orders')}
          value={data.preorders + data.cashier_sales}
          hint={t('manager.dashboard.ordersHint', {
            preorders: data.preorders,
            cashier: data.cashier_sales,
          })}
        />
        <Stat label={t('manager.dashboard.revenue')} value={formatPrice(data.revenue)} />
        <Stat
          label={t('manager.dashboard.inWork')}
          value={active}
          hint={t('manager.dashboard.pickedUp', { count: data.orders_by_status.picked_up })}
        />
        <Stat
          label={t('manager.dashboard.noShow')}
          value={data.no_show}
          hint={data.no_show_percent !== null ? `${data.no_show_percent}%` : undefined}
        />
        <Stat
          label={t('manager.dashboard.waste')}
          value={data.waste_portions}
          hint={t('manager.dashboard.portions')}
        />
        <Stat
          label={t('manager.dashboard.promotions')}
          value={data.proposed_promotions}
          hint={
            <Link to="/manager/promotions" className="text-brand-700 underline dark:text-brand-400">
              {t('manager.dashboard.promotionsHint')}
            </Link>
          }
        />
      </div>
      <Card>
        <h2 className="mb-3 font-semibold">{t('manager.dashboard.slotLoad')}</h2>
        {data.slots.length === 0 ? (
          <EmptyState>{t('manager.dashboard.noSlots')}</EmptyState>
        ) : (
          <SlotBars slots={data.slots} />
        )}
      </Card>
      {data.synthetic_history_until && (
        <p className="text-xs text-slate-500">
          {t('manager.reports.synthetic', { date: formatDay(data.synthetic_history_until) })}
        </p>
      )}
    </div>
  );
}

function SlotBars({ slots }: { slots: Dashboard['slots'] }) {
  const { t } = useTranslation();
  return (
    <div className="overflow-x-auto">
      <ul
        className="flex h-40 min-w-max items-end gap-1"
        aria-label={t('manager.dashboard.slotLoad')}
      >
        {slots.map((slot) => {
          const fill = slot.capacity ? Math.min(1, slot.booked / slot.capacity) : 0;
          const color = slot.is_closed
            ? 'bg-slate-300'
            : fill >= 1
              ? 'bg-red-500'
              : fill >= 0.7
                ? 'bg-amber-500'
                : 'bg-green-600';
          return (
            <li
              key={slot.id}
              className="flex h-full w-8 flex-col items-center justify-end"
              title={`${formatClock(slot.starts_at)} · ${slot.booked}/${slot.capacity}`}
            >
              <span className="text-[10px] text-slate-500">{slot.booked || ''}</span>
              <div className="flex h-28 w-full items-end rounded bg-slate-100 dark:bg-slate-800">
                <div
                  className={`w-full rounded ${color}`}
                  style={{ height: `${Math.max(fill * 100, slot.booked ? 4 : 0)}%` }}
                />
              </div>
              <span className="mt-1 h-3 whitespace-nowrap text-[10px] text-slate-500">
                {/:[03]0/.test(formatClock(slot.starts_at)) ? formatClock(slot.starts_at) : ''}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
