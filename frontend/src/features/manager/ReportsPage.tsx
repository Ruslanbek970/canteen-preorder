import { useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type {
  ForecastReport,
  PeakReport,
  RatingsReport,
  ReportName,
  SalesReport,
  WasteReport,
} from '@/api/types';
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
} from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';
import { formatClock, formatDay, formatPrice } from '@/lib/format';

import { ManagerShell } from './ManagerShell';
import { downloadCsv, lastDays, useReport, type Period } from './reportsApi';

const TABS: { name: ReportName; labelKey: string }[] = [
  { name: 'sales', labelKey: 'manager.reports.tabs.sales' },
  { name: 'waste', labelKey: 'manager.reports.tabs.waste' },
  { name: 'peak-hours', labelKey: 'manager.reports.tabs.peak' },
  { name: 'ratings', labelKey: 'manager.reports.tabs.ratings' },
  { name: 'forecast', labelKey: 'manager.reports.tabs.forecast' },
];
const PRESETS = [7, 28, 56];
const WASTE_COLORS = {
  expired: '#f59e0b',
  uncollected_order: '#ef4444',
  damaged: '#6366f1',
  other: '#94a3b8',
} as const;

export function ReportsPage() {
  const { t } = useTranslation();
  const errorMessage = useErrorMessage();
  const [tab, setTab] = useState<ReportName>('sales');
  const [period, setPeriod] = useState<Period>(() => lastDays(28));
  const [csvError, setCsvError] = useState<unknown>(null);
  const [downloading, setDownloading] = useState(false);

  const csv = async () => {
    setCsvError(null);
    setDownloading(true);
    try {
      await downloadCsv(tab, period);
    } catch (e) {
      setCsvError(e);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <ManagerShell
      title={t('manager.reports.title')}
      actions={
        <Button variant="secondary" disabled={downloading} onClick={() => void csv()}>
          {t('manager.reports.csv')}
        </Button>
      }
    >
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="flex gap-1" role="group" aria-label={t('manager.reports.period')}>
          {PRESETS.map((days) => {
            const preset = lastDays(days);
            const active = preset.from === period.from && preset.to === period.to;
            return (
              <button
                key={days}
                type="button"
                aria-pressed={active}
                onClick={() => setPeriod(preset)}
                className={`rounded-lg px-3 py-1.5 text-sm ${
                  active
                    ? 'bg-brand-600 font-medium text-white shadow-sm'
                    : 'border border-slate-200 bg-white text-slate-700 hover:border-brand-300 hover:text-brand-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200'
                }`}
              >
                {t('manager.reports.days', { count: days })}
              </button>
            );
          })}
        </div>
        <Field label={t('manager.reports.from')}>
          <Input
            type="date"
            value={period.from}
            max={period.to}
            onChange={(e) => e.target.value && setPeriod({ ...period, from: e.target.value })}
          />
        </Field>
        <Field label={t('manager.reports.to')}>
          <Input
            type="date"
            value={period.to}
            min={period.from}
            onChange={(e) => e.target.value && setPeriod({ ...period, to: e.target.value })}
          />
        </Field>
      </div>
      <nav className="-mx-4 mb-4 overflow-x-auto px-4" aria-label={t('manager.reports.title')}>
        <ul className="flex gap-2 border-b border-slate-200 dark:border-slate-700" role="tablist">
          {TABS.map((item) => (
            <li key={item.name}>
              <button
                type="button"
                role="tab"
                aria-selected={tab === item.name}
                onClick={() => setTab(item.name)}
                className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm ${
                  tab === item.name
                    ? 'border-brand-600 font-semibold text-brand-700'
                    : 'border-transparent text-slate-500'
                }`}
              >
                {t(item.labelKey)}
              </button>
            </li>
          ))}
        </ul>
      </nav>
      {csvError !== null && <Alert tone="error">{errorMessage(csvError)}</Alert>}
      {tab === 'sales' && <SalesTab period={period} />}
      {tab === 'waste' && <WasteTab period={period} />}
      {tab === 'peak-hours' && <PeakTab period={period} />}
      {tab === 'ratings' && <RatingsTab period={period} />}
      {tab === 'forecast' && <ForecastTab period={period} />}
    </ManagerShell>
  );
}

/** Loading, error, empty and the synthetic-data note for every report. */
function ReportFrame<T extends { synthetic_history_until: string | null }>({
  query,
  isEmpty,
  children,
}: {
  query: ReturnType<typeof useReport<T>>;
  isEmpty: (data: T) => boolean;
  children: (data: T) => ReactNode;
}) {
  const { t } = useTranslation();
  if (query.isPending) return <LoadingState />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  const data = query.data;
  return (
    <div className="space-y-4">
      {data.synthetic_history_until && (
        <Alert tone="info">
          {t('manager.reports.synthetic', { date: formatDay(data.synthetic_history_until) })}
        </Alert>
      )}
      {isEmpty(data) ? <EmptyState>{t('manager.reports.empty')}</EmptyState> : children(data)}
    </div>
  );
}

function Numbers({ items }: { items: [string, ReactNode][] }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {items.map(([label, value]) => (
        <Card key={label}>
          <p className="text-sm text-slate-500">{label}</p>
          <p className="mt-1 text-xl font-semibold">{value}</p>
        </Card>
      ))}
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <h2 className="mb-2 font-semibold">{title}</h2>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          {children as React.ReactElement}
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

function Table({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[300px] text-left text-sm">
        <thead className="text-slate-500">
          <tr>
            {head.map((h) => (
              <th key={h} className="py-2 pr-3 font-normal">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-slate-100 dark:border-slate-800">
              {row.map((cell, j) => (
                <td key={j} className="py-2 pr-3">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const percent = (value: number | null) => (value === null ? '—' : `${value}%`);

function SalesTab({ period }: { period: Period }) {
  const { t } = useTranslation();
  const query = useReport<SalesReport>('sales', period);
  return (
    <ReportFrame query={query} isEmpty={(d) => d.days.length === 0}>
      {(data) => (
        <>
          <Numbers
            items={[
              [t('manager.reports.revenue'), formatPrice(data.totals.revenue)],
              [t('manager.reports.orders'), data.totals.orders],
              [
                t('manager.reports.averageCheck'),
                data.totals.average_check ? formatPrice(data.totals.average_check) : '—',
              ],
              [t('manager.reports.preorderShare'), percent(data.totals.preorder_share)],
            ]}
          />
          <ChartCard title={t('manager.reports.revenueByDay')}>
            <LineChart
              data={data.days.map((d) => ({
                day: formatDay(d.date),
                revenue: Number(d.revenue),
                orders: d.orders,
              }))}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="day" fontSize={12} />
              <YAxis yAxisId="revenue" fontSize={12} width={70} />
              <YAxis yAxisId="orders" orientation="right" fontSize={12} />
              <Tooltip
                formatter={(value: number, name: string) =>
                  name === t('manager.reports.revenue') ? formatPrice(value) : value
                }
              />
              <Legend />
              <Line
                yAxisId="revenue"
                dataKey="revenue"
                name={t('manager.reports.revenue')}
                stroke="#16a34a"
                dot={false}
              />
              <Line
                yAxisId="orders"
                dataKey="orders"
                name={t('manager.reports.orders')}
                stroke="#64748b"
                dot={false}
              />
            </LineChart>
          </ChartCard>
          <Card>
            <h2 className="mb-2 font-semibold">{t('manager.reports.byDish')}</h2>
            <Table
              head={[
                t('manager.reports.dish'),
                t('manager.reports.portions'),
                t('manager.reports.revenue'),
              ]}
              rows={data.dishes.map((d) => [d.name, d.portions, formatPrice(d.revenue)])}
            />
          </Card>
        </>
      )}
    </ReportFrame>
  );
}

function WasteTab({ period }: { period: Period }) {
  const { t } = useTranslation();
  const query = useReport<WasteReport>('waste', period);
  const reasons = Object.keys(WASTE_COLORS) as (keyof typeof WASTE_COLORS)[];
  return (
    <ReportFrame query={query} isEmpty={(d) => d.dishes.length === 0}>
      {(data) => (
        <>
          <Numbers
            items={[
              [t('manager.reports.wasteTotal'), data.total],
              [t('manager.reports.wastePerDay'), data.per_day ?? '—'],
              [t('manager.reports.wasteShare'), percent(data.percent_of_planned)],
              [t('kitchen.waste.reasons.uncollected_order'), data.by_reason.uncollected_order],
            ]}
          />
          <ChartCard title={t('manager.reports.wasteByDay')}>
            <BarChart data={data.days.map((d) => ({ day: formatDay(d.date), ...d.by_reason }))}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="day" fontSize={12} />
              <YAxis fontSize={12} />
              <Tooltip />
              <Legend />
              {reasons.map((reason) => (
                <Bar
                  key={reason}
                  dataKey={reason}
                  stackId="waste"
                  name={t(`kitchen.waste.reasons.${reason}`)}
                  fill={WASTE_COLORS[reason]}
                />
              ))}
            </BarChart>
          </ChartCard>
          <Card>
            <h2 className="mb-2 font-semibold">{t('manager.reports.byDish')}</h2>
            <Table
              head={[
                t('manager.reports.dish'),
                t('manager.reports.wasted'),
                t('manager.reports.planned'),
                t('manager.reports.wasteShare'),
              ]}
              rows={data.dishes.map((d) => [
                d.name,
                d.portions,
                d.planned,
                percent(d.percent_of_planned),
              ])}
            />
          </Card>
        </>
      )}
    </ReportFrame>
  );
}

function PeakTab({ period }: { period: Period }) {
  const { t } = useTranslation();
  const query = useReport<PeakReport>('peak-hours', period);
  return (
    <ReportFrame query={query} isEmpty={(d) => d.slots.length === 0}>
      {(data) => {
        const top = [...data.slots].sort((a, b) => b.orders - a.orders).slice(0, 3);
        return (
          <>
            <Numbers
              items={[
                [t('manager.reports.daysWithOrders'), data.days],
                [t('manager.reports.busiest'), top.map((s) => formatClock(s.starts_at)).join(', ')],
                [t('manager.reports.noShowShare'), percent(data.no_show_percent)],
                [
                  t('manager.reports.preordersPerDay'),
                  data.days
                    ? Math.round(data.slots.reduce((sum, s) => sum + s.orders, 0) / data.days)
                    : '—',
                ],
              ]}
            />
            <ChartCard title={t('manager.reports.perSlot')}>
              <BarChart
                data={data.slots.map((s) => ({
                  slot: formatClock(s.starts_at),
                  perDay: s.per_day,
                }))}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="slot" fontSize={11} interval={1} />
                <YAxis fontSize={12} />
                <Tooltip />
                <Bar dataKey="perDay" name={t('manager.reports.ordersPerDay')} fill="#16a34a" />
              </BarChart>
            </ChartCard>
            <Card>
              <h2 className="mb-2 font-semibold">{t('manager.reports.byWeekday')}</h2>
              <Table
                head={[t('manager.reports.weekday'), t('manager.reports.ordersPerDay')]}
                rows={data.weekdays.map((w) => [
                  t(`manager.reports.weekdays.${w.weekday}`),
                  w.per_day,
                ])}
              />
            </Card>
          </>
        );
      }}
    </ReportFrame>
  );
}

function RatingsTab({ period }: { period: Period }) {
  const { t } = useTranslation();
  const query = useReport<RatingsReport>('ratings', period);
  return (
    <ReportFrame query={query} isEmpty={(d) => d.dishes.length === 0}>
      {(data) => (
        <ul className="grid gap-3 md:grid-cols-2">
          {data.dishes.map((dish) => (
            <li key={dish.dish_id}>
              <Card>
                <div className="flex items-baseline justify-between gap-2">
                  <h2 className="font-semibold">{dish.name}</h2>
                  <span className="text-lg font-semibold">★ {dish.rating?.toFixed(1) ?? '—'}</span>
                </div>
                <p className="text-xs text-slate-500">
                  {t('manager.reports.reviews', { count: dish.count })}
                </p>
                <ul className="mt-2 space-y-0.5" aria-label={t('manager.reports.distribution')}>
                  {[5, 4, 3, 2, 1].map((stars) => {
                    const n = dish.distribution[stars - 1] ?? 0;
                    return (
                      <li key={stars} className="flex items-center gap-2 text-xs">
                        <span className="w-4">{stars}</span>
                        <div className="h-2 flex-1 rounded bg-slate-100 dark:bg-slate-800">
                          <div
                            className="h-2 rounded bg-amber-400"
                            style={{ width: `${dish.count ? (100 * n) / dish.count : 0}%` }}
                          />
                        </div>
                        <span className="w-8 text-right text-slate-500">{n}</span>
                      </li>
                    );
                  })}
                </ul>
                {dish.last_comments.length > 0 && (
                  <ul className="mt-2 space-y-1 text-sm">
                    {dish.last_comments.map((c) => (
                      <li key={c.created_at} className="text-slate-600 dark:text-slate-300">
                        <span className="text-amber-500">{'★'.repeat(c.rating)}</span> {c.comment}
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </ReportFrame>
  );
}

const MODEL_NAMES: Record<string, string> = {
  baseline_avg: 'baseline_avg',
  gbm_v1: 'gbm_v1',
};

function ForecastTab({ period }: { period: Period }) {
  const { t } = useTranslation();
  const query = useReport<ForecastReport>('forecast', period);
  return (
    <ReportFrame query={query} isEmpty={(d) => d.days.length === 0 && d.upcoming.length === 0}>
      {(data) => (
        <>
          <p className="max-w-3xl text-sm text-slate-500">{t('manager.reports.forecastIntro')}</p>
          {data.days.length > 0 && (
            <>
              <Numbers
                items={[
                  ...data.models.map((m): [string, ReactNode] => [
                    t('manager.reports.maeOf', { model: MODEL_NAMES[m.model] ?? m.model }),
                    t('manager.reports.portionsValue', { value: m.mae.toFixed(1) }),
                  ]),
                  [
                    t('manager.reports.servedMape'),
                    percent(data.served ? Number(data.served.mape.toFixed(1)) : null),
                  ],
                  [
                    t('manager.reports.better'),
                    data.better ? (MODEL_NAMES[data.better] ?? data.better) : '—',
                  ],
                ]}
              />
              <ChartCard title={t('manager.reports.forecastByDay')}>
                <LineChart
                  data={data.days.map((d) => ({
                    day: formatDay(d.date),
                    actual: d.actual,
                    baseline: d.baseline_avg === null ? null : Math.round(d.baseline_avg),
                    gbm: d.gbm_v1 === null ? null : Math.round(d.gbm_v1),
                  }))}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="day" fontSize={12} />
                  <YAxis fontSize={12} width={50} />
                  <Tooltip />
                  <Legend />
                  <Line
                    dataKey="actual"
                    name={t('manager.reports.actual')}
                    stroke="#0f172a"
                    strokeWidth={2}
                  />
                  <Line
                    dataKey="baseline"
                    name="baseline_avg"
                    stroke="#94a3b8"
                    strokeDasharray="5 4"
                  />
                  <Line dataKey="gbm" name="gbm_v1" stroke="#16a34a" />
                </LineChart>
              </ChartCard>
              <Card>
                <h2 className="mb-2 font-semibold">{t('manager.reports.models')}</h2>
                <Table
                  head={[t('manager.reports.model'), 'MAE', 'MAPE', t('manager.reports.positions')]}
                  rows={data.models.map((m) => [
                    <span key="name" className="flex items-center gap-2">
                      {MODEL_NAMES[m.model] ?? m.model}
                      {m.model === data.better && (
                        <Badge tone="green">{t('manager.reports.moreAccurate')}</Badge>
                      )}
                    </span>,
                    m.mae.toFixed(2),
                    percent(Number(m.mape.toFixed(1))),
                    m.n,
                  ])}
                />
              </Card>
              <Card>
                <h2 className="mb-2 font-semibold">{t('manager.reports.byDish')}</h2>
                <Table
                  head={[
                    t('manager.reports.dish'),
                    t('manager.reports.actual'),
                    t('manager.reports.forecast'),
                    'MAE',
                  ]}
                  rows={data.dishes.map((d) => [d.dish_name, d.actual, d.forecast, d.mae])}
                />
              </Card>
            </>
          )}
          {data.upcoming.length > 0 && (
            <Card>
              <h2 className="mb-2 font-semibold">{t('manager.reports.upcoming')}</h2>
              <Table
                head={[
                  t('manager.reports.day'),
                  t('manager.reports.servedModel'),
                  'MAE baseline_avg',
                  'MAE gbm_v1',
                ]}
                rows={data.upcoming.map((u) => {
                  const mae = (name: string) =>
                    u.backtest.find((b) => b.model === name)?.mae.toFixed(2) ?? '—';
                  return [formatDay(u.target_date), u.model, mae('baseline_avg'), mae('gbm_v1')];
                })}
              />
            </Card>
          )}
        </>
      )}
    </ReportFrame>
  );
}
