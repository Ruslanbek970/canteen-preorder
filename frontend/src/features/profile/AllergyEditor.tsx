import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { apiGet } from '@/api/client';
import type { Allergen, Severity } from '@/api/types';
import { LoadingState } from '@/components/ui';
import { allergenName } from '@/lib/names';

export interface AllergyChoice {
  allergen_id: number;
  severity: Severity;
}

const SEVERITIES: Severity[] = ['mild', 'moderate', 'severe'];

/** Checkbox list of allergens with a severity per checked allergen (SPEC 7.3). */
export function AllergyEditor({
  value,
  onChange,
  disabled,
}: {
  value: AllergyChoice[];
  onChange: (value: AllergyChoice[]) => void;
  disabled?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const allergens = useQuery({
    queryKey: ['allergens'],
    queryFn: () => apiGet<Allergen[]>('/allergens'),
    staleTime: Infinity,
  });
  if (allergens.isPending) return <LoadingState />;
  const byId = new Map(value.map((v) => [v.allergen_id, v]));

  function toggle(id: number, checked: boolean) {
    if (checked) onChange([...value, { allergen_id: id, severity: 'moderate' }]);
    else onChange(value.filter((v) => v.allergen_id !== id));
  }

  function setSeverity(id: number, severity: Severity) {
    onChange(value.map((v) => (v.allergen_id === id ? { ...v, severity } : v)));
  }

  return (
    <ul className="divide-y divide-slate-200 dark:divide-slate-800">
      {allergens.data?.map((a) => {
        const chosen = byId.get(a.id);
        return (
          <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                className="h-5 w-5"
                disabled={disabled}
                checked={Boolean(chosen)}
                onChange={(e) => toggle(a.id, e.target.checked)}
              />
              {allergenName(a, i18n.resolvedLanguage)}
            </label>
            {chosen && (
              <select
                aria-label={t('allergy.severity')}
                className="rounded border border-slate-300 bg-transparent px-2 py-1 text-sm dark:border-slate-700"
                value={chosen.severity}
                disabled={disabled}
                onChange={(e) => setSeverity(a.id, e.target.value as Severity)}
              >
                {SEVERITIES.map((s) => (
                  <option key={s} value={s}>
                    {t(`allergy.${s}`)}
                  </option>
                ))}
              </select>
            )}
          </li>
        );
      })}
    </ul>
  );
}
