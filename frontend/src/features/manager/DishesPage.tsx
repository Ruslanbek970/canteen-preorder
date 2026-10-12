import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet, apiPatch, apiPost } from '@/api/client';
import type { Category, Ingredient, ManagerDish } from '@/api/types';
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
import { formatPrice } from '@/lib/format';
import { allergenName } from '@/lib/names';

import { ManagerShell } from './ManagerShell';

const DISHES_KEY = ['manager', 'dishes'];

export function DishesPage() {
  const { t, i18n } = useTranslation();
  const dishes = useQuery({
    queryKey: DISHES_KEY,
    queryFn: () => apiGet<ManagerDish[]>('/manager/dishes'),
  });
  const [editing, setEditing] = useState<ManagerDish | 'new' | null>(null);

  return (
    <ManagerShell
      title={t('manager.dishes.title')}
      actions={<Button onClick={() => setEditing('new')}>{t('manager.dishes.new')}</Button>}
    >
      {editing && (
        <DishForm
          key={editing === 'new' ? 'new' : editing.id}
          dish={editing === 'new' ? null : editing}
          onDone={() => setEditing(null)}
        />
      )}
      <Card className="overflow-x-auto p-0">
        {dishes.isPending ? (
          <LoadingState />
        ) : dishes.isError ? (
          <ErrorState error={dishes.error} onRetry={() => void dishes.refetch()} />
        ) : dishes.data.length === 0 ? (
          <EmptyState>{t('manager.dishes.empty')}</EmptyState>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left dark:bg-slate-800">
              <tr>
                <th className="p-2">{t('manager.dishes.name')}</th>
                <th className="p-2">{t('manager.dishes.category')}</th>
                <th className="p-2 text-right">{t('manager.dishes.price')}</th>
                <th className="p-2">{t('menu.allergens')}</th>
                <th className="p-2" />
              </tr>
            </thead>
            <tbody>
              {dishes.data.map((d) => (
                <tr key={d.id} className="border-t border-slate-100 dark:border-slate-800">
                  <td className="p-2">
                    {d.name_ru}
                    {!d.is_active && (
                      <span className="ml-2">
                        <Badge>{t('manager.dishes.inactive')}</Badge>
                      </span>
                    )}
                  </td>
                  <td className="p-2">{d.category_name}</td>
                  <td className="p-2 text-right">{formatPrice(d.base_price)}</td>
                  <td className="p-2">
                    <div className="flex flex-wrap gap-1">
                      {d.allergens.map((a) => (
                        <Badge key={a.id} tone="amber">
                          {allergenName(a, i18n.resolvedLanguage)}
                        </Badge>
                      ))}
                    </div>
                  </td>
                  <td className="p-2 text-right">
                    <Button variant="ghost" onClick={() => setEditing(d)}>
                      {t('common.edit')}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </ManagerShell>
  );
}

interface RecipeRow {
  ingredient_id: string;
  quantity: string;
}

function DishForm({ dish, onDone }: { dish: ManagerDish | null; onDone: () => void }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const categories = useQuery({
    queryKey: ['categories'],
    queryFn: () => apiGet<Category[]>('/dish-categories'),
  });
  const ingredients = useQuery({
    queryKey: ['manager', 'ingredients'],
    queryFn: () => apiGet<Ingredient[]>('/manager/ingredients'),
  });
  const [form, setForm] = useState({
    name_ru: dish?.name_ru ?? '',
    name_kk: dish?.name_kk ?? '',
    description: dish?.description ?? '',
    category_id: dish ? String(dish.category_id) : '',
    base_price: dish ? String(Number(dish.base_price)) : '',
    portion_grams: dish?.portion_grams ? String(dish.portion_grams) : '',
    calories: dish?.calories !== null && dish?.calories !== undefined ? String(dish.calories) : '',
    protein_g: dish?.protein_g ?? '',
    fat_g: dish?.fat_g ?? '',
    carbs_g: dish?.carbs_g ?? '',
    shelf_life_hours: String(dish?.shelf_life_hours ?? 4),
    is_halal: dish?.is_halal ?? true,
    is_vegetarian: dish?.is_vegetarian ?? false,
    is_active: dish?.is_active ?? true,
  });
  const [recipe, setRecipe] = useState<RecipeRow[]>(
    dish?.ingredients.map((i) => ({
      ingredient_id: String(i.ingredient_id),
      quantity: String(Number(i.quantity)),
    })) ?? [],
  );
  const set = (key: keyof typeof form, value: string | boolean) =>
    setForm((f) => ({ ...f, [key]: value }));

  // Allergen preview from the chosen ingredients (SPEC 9.4, item 3).
  const preview = useMemo(() => {
    const byId = new Map((ingredients.data ?? []).map((i) => [String(i.id), i]));
    const seen = new Map<number, Ingredient['allergens'][number]>();
    for (const row of recipe)
      for (const a of byId.get(row.ingredient_id)?.allergens ?? []) seen.set(a.id, a);
    return [...seen.values()];
  }, [recipe, ingredients.data]);

  const num = (v: string) => (v === '' ? null : v);
  const save = useMutation({
    mutationFn: () => {
      const body = {
        name_ru: form.name_ru,
        name_kk: num(form.name_kk),
        description: num(form.description),
        category_id: Number(form.category_id),
        base_price: form.base_price,
        portion_grams: form.portion_grams ? Number(form.portion_grams) : null,
        calories: form.calories ? Number(form.calories) : null,
        protein_g: num(String(form.protein_g)),
        fat_g: num(String(form.fat_g)),
        carbs_g: num(String(form.carbs_g)),
        shelf_life_hours: Number(form.shelf_life_hours),
        is_halal: form.is_halal,
        is_vegetarian: form.is_vegetarian,
        is_active: form.is_active,
        ingredients: recipe
          .filter((r) => r.ingredient_id && r.quantity)
          .map((r) => ({ ingredient_id: Number(r.ingredient_id), quantity: r.quantity })),
      };
      return dish
        ? apiPatch<ManagerDish>(`/manager/dishes/${dish.id}`, body)
        : apiPost<ManagerDish>('/manager/dishes', body);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: DISHES_KEY });
      void queryClient.invalidateQueries({ queryKey: ['menu'] });
      onDone();
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };

  return (
    <Card className="mb-4">
      <form className="space-y-4" onSubmit={submit}>
        <h2 className="text-lg font-medium">
          {dish ? t('manager.dishes.edit') : t('manager.dishes.new')}
        </h2>
        {save.isError && <Alert>{errorMessage(save.error)}</Alert>}
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t('manager.dishes.nameRu')}>
            <Input required value={form.name_ru} onChange={(e) => set('name_ru', e.target.value)} />
          </Field>
          <Field label={t('manager.dishes.nameKk')}>
            <Input value={form.name_kk} onChange={(e) => set('name_kk', e.target.value)} />
          </Field>
          <Field label={t('manager.dishes.category')}>
            <Select
              required
              value={form.category_id}
              onChange={(e) => set('category_id', e.target.value)}
            >
              <option value="">—</option>
              {categories.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t('manager.dishes.price')}>
            <Input
              required
              type="number"
              min="1"
              step="1"
              value={form.base_price}
              onChange={(e) => set('base_price', e.target.value)}
            />
          </Field>
          <Field label={t('menu.weight')}>
            <Input
              type="number"
              min="1"
              value={form.portion_grams}
              onChange={(e) => set('portion_grams', e.target.value)}
            />
          </Field>
          <Field label={t('manager.dishes.shelfLife')}>
            <Input
              required
              type="number"
              min="1"
              value={form.shelf_life_hours}
              onChange={(e) => set('shelf_life_hours', e.target.value)}
            />
          </Field>
          <Field label={t('menu.calories')}>
            <Input
              type="number"
              min="0"
              value={form.calories}
              onChange={(e) => set('calories', e.target.value)}
            />
          </Field>
          <div className="grid grid-cols-3 gap-2">
            <Field label={t('menu.protein')}>
              <Input
                type="number"
                min="0"
                step="0.1"
                value={form.protein_g}
                onChange={(e) => set('protein_g', e.target.value)}
              />
            </Field>
            <Field label={t('menu.fat')}>
              <Input
                type="number"
                min="0"
                step="0.1"
                value={form.fat_g}
                onChange={(e) => set('fat_g', e.target.value)}
              />
            </Field>
            <Field label={t('menu.carbs')}>
              <Input
                type="number"
                min="0"
                step="0.1"
                value={form.carbs_g}
                onChange={(e) => set('carbs_g', e.target.value)}
              />
            </Field>
          </div>
        </div>
        <Field label={t('manager.dishes.description')}>
          <textarea
            className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"
            rows={2}
            value={form.description}
            onChange={(e) => set('description', e.target.value)}
          />
        </Field>
        <div className="flex flex-wrap gap-4 text-sm">
          {(['is_halal', 'is_vegetarian', 'is_active'] as const).map((key) => (
            <label key={key} className="flex items-center gap-2">
              <input
                type="checkbox"
                className="h-5 w-5"
                checked={form[key]}
                onChange={(e) => set(key, e.target.checked)}
              />
              {t(`manager.dishes.${key}`)}
            </label>
          ))}
        </div>
        <fieldset>
          <legend className="mb-2 font-medium">{t('manager.dishes.recipe')}</legend>
          <div className="space-y-2">
            {recipe.map((row, idx) => (
              <div key={idx} className="flex gap-2">
                <Select
                  aria-label={t('manager.dishes.ingredient')}
                  value={row.ingredient_id}
                  onChange={(e) =>
                    setRecipe(
                      recipe.map((r, i) =>
                        i === idx ? { ...r, ingredient_id: e.target.value } : r,
                      ),
                    )
                  }
                >
                  <option value="">—</option>
                  {ingredients.data?.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.name} ({t(`units.${i.unit}`)})
                    </option>
                  ))}
                </Select>
                <Input
                  aria-label={t('manager.dishes.quantity')}
                  className="w-28"
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={row.quantity}
                  onChange={(e) =>
                    setRecipe(
                      recipe.map((r, i) => (i === idx ? { ...r, quantity: e.target.value } : r)),
                    )
                  }
                />
                <Button
                  variant="ghost"
                  aria-label={t('common.remove')}
                  onClick={() => setRecipe(recipe.filter((_, i) => i !== idx))}
                >
                  ✕
                </Button>
              </div>
            ))}
            <Button
              variant="secondary"
              onClick={() => setRecipe([...recipe, { ingredient_id: '', quantity: '' }])}
            >
              {t('manager.dishes.addIngredient')}
            </Button>
          </div>
          <p className="mt-3 text-sm">
            {t('manager.dishes.allergenPreview')}:{' '}
            {preview.length === 0
              ? t('menu.noAllergens')
              : preview.map((a) => allergenName(a, i18n.resolvedLanguage)).join(', ')}
          </p>
        </fieldset>
        <div className="flex gap-2">
          <Button type="submit" disabled={save.isPending}>
            {t('common.save')}
          </Button>
          <Button variant="secondary" onClick={onDone}>
            {t('common.cancel')}
          </Button>
        </div>
      </form>
    </Card>
  );
}
