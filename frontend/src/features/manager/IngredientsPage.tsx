import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet, apiPost } from '@/api/client';
import type { Allergen, Ingredient } from '@/api/types';
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
import { allergenName } from '@/lib/names';

import { ManagerShell } from './ManagerShell';

export function IngredientsPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const ingredients = useQuery({
    queryKey: ['manager', 'ingredients'],
    queryFn: () => apiGet<Ingredient[]>('/manager/ingredients'),
  });
  const allergens = useQuery({
    queryKey: ['allergens'],
    queryFn: () => apiGet<Allergen[]>('/allergens'),
  });
  const [name, setName] = useState('');
  const [unit, setUnit] = useState<'g' | 'ml' | 'pcs'>('g');
  const [chosen, setChosen] = useState<number[]>([]);
  const create = useMutation({
    mutationFn: () =>
      apiPost<Ingredient>('/manager/ingredients', { name, unit, allergen_ids: chosen }),
    onSuccess: () => {
      setName('');
      setChosen([]);
      void queryClient.invalidateQueries({ queryKey: ['manager', 'ingredients'] });
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };

  return (
    <ManagerShell title={t('manager.ingredients.title')}>
      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <Card className="overflow-x-auto p-0">
          {ingredients.isPending ? (
            <LoadingState />
          ) : ingredients.isError ? (
            <ErrorState error={ingredients.error} onRetry={() => void ingredients.refetch()} />
          ) : ingredients.data.length === 0 ? (
            <EmptyState>{t('manager.ingredients.empty')}</EmptyState>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left dark:bg-slate-800">
                <tr>
                  <th className="p-2">{t('manager.ingredients.name')}</th>
                  <th className="p-2">{t('manager.ingredients.unit')}</th>
                  <th className="p-2">{t('menu.allergens')}</th>
                </tr>
              </thead>
              <tbody>
                {ingredients.data.map((i) => (
                  <tr key={i.id} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="p-2">{i.name}</td>
                    <td className="p-2">{t(`units.${i.unit}`)}</td>
                    <td className="p-2">
                      <div className="flex flex-wrap gap-1">
                        {i.allergens.map((a) => (
                          <Badge key={a.id} tone="amber">
                            {allergenName(a, i18n.resolvedLanguage)}
                          </Badge>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
        <Card>
          <form className="space-y-3" onSubmit={submit}>
            <h2 className="font-medium">{t('manager.ingredients.add')}</h2>
            {create.isError && <Alert>{errorMessage(create.error)}</Alert>}
            <Field label={t('manager.ingredients.name')}>
              <Input required value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label={t('manager.ingredients.unit')}>
              <Select value={unit} onChange={(e) => setUnit(e.target.value as typeof unit)}>
                <option value="g">{t('units.g')}</option>
                <option value="ml">{t('units.ml')}</option>
                <option value="pcs">{t('units.pcs')}</option>
              </Select>
            </Field>
            <fieldset>
              <legend className="mb-1 text-sm font-medium">{t('menu.allergens')}</legend>
              <div className="grid grid-cols-2 gap-1">
                {allergens.data?.map((a) => (
                  <label key={a.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={chosen.includes(a.id)}
                      onChange={(e) =>
                        setChosen(
                          e.target.checked ? [...chosen, a.id] : chosen.filter((x) => x !== a.id),
                        )
                      }
                    />
                    {allergenName(a, i18n.resolvedLanguage)}
                  </label>
                ))}
              </div>
            </fieldset>
            <Button type="submit" className="w-full" disabled={create.isPending}>
              {t('common.add')}
            </Button>
          </form>
        </Card>
      </div>
    </ManagerShell>
  );
}
