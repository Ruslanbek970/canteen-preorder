import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router-dom';

import { Button, ErrorState, LoadingState } from '@/components/ui';
import { formatClock, formatDay } from '@/lib/format';

import { useLabels } from './api';

/** Stickers 58×40 mm, printed from the browser (SPEC 7.8). */
export function LabelsPage() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const ids = (params.get('ids') ?? '')
    .split(',')
    .map(Number)
    .filter((n) => Number.isInteger(n) && n > 0);
  const labels = useLabels(ids);

  useEffect(() => {
    if (labels.data && labels.data.length > 0 && params.get('print') !== '0') {
      const timer = setTimeout(() => window.print(), 300);
      return () => clearTimeout(timer);
    }
  }, [labels.data, params]);

  if (labels.isPending) return <LoadingState />;
  if (labels.isError) return <ErrorState error={labels.error} />;

  return (
    <section className="labels-root p-4">
      <style>{`@media print {
  @page { size: 58mm 40mm; margin: 0; }
  html, body { margin: 0 !important; padding: 0 !important; background: #fff !important; }
  header, .no-print { display: none !important; }
  main, .labels-root, .label-list { margin: 0 !important; padding: 0 !important; max-width: none !important; display: block !important; }
  .label { border: none !important; margin: 0 !important; break-inside: avoid; }
  .label:not(:last-child) { break-after: page; }
  .label * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}`}</style>
      <div className="no-print mb-4 flex gap-2">
        <Button onClick={() => window.print()}>{t('kitchen.print')}</Button>
        <Link to="/kitchen" className="self-center text-brand-700 dark:text-brand-400">
          ← {t('kitchen.tabs.board')}
        </Link>
      </div>
      <div className="label-list flex flex-wrap gap-3">
        {labels.data.map((l) => (
          <article
            key={l.order_id}
            className="label flex flex-col overflow-hidden border border-dashed border-slate-400 bg-white p-[2mm] text-black"
            style={{
              width: '58mm',
              height: '40mm',
              fontSize: '8pt',
              lineHeight: 1.15,
              boxSizing: 'border-box',
            }}
          >
            <div className="flex items-baseline justify-between">
              <span style={{ fontSize: '18pt', fontWeight: 800, lineHeight: 1 }}>
                {l.order_number}
              </span>
              <span style={{ fontSize: '10pt', fontWeight: 700 }}>
                {l.starts_at ? formatClock(l.starts_at) : ''}
              </span>
            </div>
            <div style={{ fontSize: '7pt' }}>
              {l.canteen_name} · {formatDay(l.service_date)}
            </div>
            <ul className="mt-[1mm] flex-1 overflow-hidden">
              {l.items.map((i) => (
                <li key={i.menu_item_id}>
                  {i.name} × {i.quantity}
                </li>
              ))}
            </ul>
            {l.allergy_flag && (
              <div
                style={{
                  fontWeight: 800,
                  fontSize: '7.5pt',
                  background: '#000',
                  color: '#fff',
                  padding: '0.5mm 1mm',
                }}
              >
                {l.allergy_flag}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
