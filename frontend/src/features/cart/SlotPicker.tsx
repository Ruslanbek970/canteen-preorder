import { useTranslation } from 'react-i18next';

import type { SlotsResponse } from '@/api/types';
import { Badge } from '@/components/ui';
import { formatClock } from '@/lib/format';

/** Slot grid with an explanation of why some slots are not offered (SPEC 7.4). */
export function SlotPicker({
  data,
  value,
  onChange,
}: {
  data: SlotsResponse;
  value: number | null;
  onChange: (id: number) => void;
}) {
  const { t } = useTranslation();
  const { hidden } = data;
  const reasons = [
    hidden.by_schedule > 0 && t('slots.hiddenSchedule', { count: hidden.by_schedule }),
    hidden.too_late > 0 &&
      t('slots.hiddenTooLate', { count: hidden.too_late, minutes: data.cutoff_minutes }),
    hidden.full > 0 && t('slots.hiddenFull', { count: hidden.full }),
    hidden.closed > 0 && t('slots.hiddenClosed', { count: hidden.closed }),
  ].filter(Boolean) as string[];

  return (
    <fieldset>
      <legend className="mb-2 font-semibold">{t('slots.title')}</legend>
      {data.slots.length === 0 ? (
        <p className="rounded-lg bg-slate-100 p-3 text-sm dark:bg-slate-800">
          {data.total === 0 ? t('slots.noneToday') : t('slots.noneLeft')}
        </p>
      ) : (
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
          {data.slots.map((slot) => {
            const selected = slot.id === value;
            return (
              <button
                key={slot.id}
                type="button"
                aria-pressed={selected}
                onClick={() => onChange(slot.id)}
                className={`flex min-h-[56px] flex-col items-center justify-center rounded-lg border px-1 py-2 text-sm ${
                  selected
                    ? 'border-green-600 bg-green-600 text-white'
                    : 'border-slate-300 bg-white dark:border-slate-700 dark:bg-slate-900'
                }`}
              >
                <span className="font-semibold">{formatClock(slot.starts_at)}</span>
                <span className={`text-xs ${selected ? 'text-green-50' : 'text-slate-500'}`}>
                  {t('slots.free', { count: slot.free })}
                </span>
                {slot.discount_percent ? <Badge tone="red">−{slot.discount_percent}%</Badge> : null}
              </button>
            );
          })}
        </div>
      )}
      {reasons.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-slate-500">
          {reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}
    </fieldset>
  );
}
