import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { apiDelete, apiGet, apiPatch, apiPut } from '@/api/client';
import type { Group, Language, Me, MyAllergens } from '@/api/types';
import {
  Alert,
  Button,
  Card,
  ErrorState,
  Field,
  Input,
  LoadingState,
  PageTitle,
  Select,
} from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';
import { ME_KEY, useLogout, useMe } from '@/features/auth/useMe';
import { SUPPORTED_LANGUAGES } from '@/i18n';

import { AllergyEditor, type AllergyChoice } from './AllergyEditor';

const LANGUAGE_NAMES: Record<Language, string> = { ru: 'Русский', kk: 'Қазақша', en: 'English' };

export function ProfilePage() {
  const { t } = useTranslation();
  const me = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  if (me.isPending) return <LoadingState />;
  if (me.isError) return <ErrorState error={me.error} onRetry={() => void me.refetch()} />;
  const customer = me.data.role === 'student' || me.data.role === 'teacher';
  return (
    <section className="mx-auto max-w-xl space-y-4 p-4">
      <PageTitle>{t('pages.profile')}</PageTitle>
      <ProfileForm me={me.data} key={me.data.id} />
      {customer && <AllergySection />}
      {customer && (
        <Card>
          <h2 className="font-medium">{t('profile.loyalty')}</h2>
          <p className="mt-1 text-3xl font-semibold">{me.data.loyalty_points}</p>
          <p className="text-sm text-slate-500">{t('profile.loyaltyHint')}</p>
        </Card>
      )}
      <Button
        variant="secondary"
        className="w-full"
        onClick={() => void logout().then(() => navigate('/login'))}
      >
        {t('auth.logout')}
      </Button>
    </section>
  );
}

function ProfileForm({ me }: { me: Me }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const groups = useQuery({
    queryKey: ['groups'],
    queryFn: () => apiGet<Group[]>('/groups'),
    enabled: me.role === 'student',
  });
  const [form, setForm] = useState({
    full_name: me.full_name,
    preferred_language: me.preferred_language,
    group_id: me.group_id ? String(me.group_id) : '',
    marketing_opt_out: me.marketing_opt_out,
  });
  const save = useMutation({
    mutationFn: () =>
      apiPatch<Me>('/me', {
        full_name: form.full_name,
        preferred_language: form.preferred_language,
        marketing_opt_out: form.marketing_opt_out,
        ...(me.role === 'student' && form.group_id ? { group_id: Number(form.group_id) } : {}),
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(ME_KEY, data);
      void i18n.changeLanguage(data.preferred_language);
    },
  });

  return (
    <Card className="space-y-4">
      <p className="text-sm text-slate-500">
        {me.email} · {t(`roles.${me.role}`)}
        {me.canteen_name ? ` · ${me.canteen_name}` : ''}
      </p>
      {save.isError && <Alert>{errorMessage(save.error)}</Alert>}
      {save.isSuccess && <Alert tone="success">{t('common.saved')}</Alert>}
      <Field label={t('auth.fullName')}>
        <Input
          value={form.full_name}
          onChange={(e) => setForm({ ...form, full_name: e.target.value })}
        />
      </Field>
      {me.role === 'student' && (
        <Field label={t('auth.group')}>
          <Select
            value={form.group_id}
            onChange={(e) => setForm({ ...form, group_id: e.target.value })}
          >
            {groups.data?.map((g) => (
              <option key={g.id} value={g.id}>
                {g.code}
              </option>
            ))}
          </Select>
        </Field>
      )}
      <Field label={t('nav.language')}>
        <Select
          value={form.preferred_language}
          onChange={(e) => setForm({ ...form, preferred_language: e.target.value as Language })}
        >
          {SUPPORTED_LANGUAGES.map((l) => (
            <option key={l} value={l}>
              {LANGUAGE_NAMES[l]}
            </option>
          ))}
        </Select>
      </Field>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          className="h-5 w-5"
          checked={!form.marketing_opt_out}
          onChange={(e) => setForm({ ...form, marketing_opt_out: !e.target.checked })}
        />
        {t('profile.marketing')}
      </label>
      <Button onClick={() => save.mutate()} disabled={save.isPending}>
        {t('common.save')}
      </Button>
    </Card>
  );
}

function AllergySection() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ['me', 'allergens'],
    queryFn: () => apiGet<MyAllergens>('/me/allergens'),
  });
  if (query.isPending) return <LoadingState />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  return (
    <AllergyForm
      key={query.dataUpdatedAt}
      initial={query.data}
      onSaved={(data) => {
        queryClient.setQueryData(['me', 'allergens'], data);
        void queryClient.invalidateQueries({ queryKey: ['menu'] });
        void queryClient.invalidateQueries({ queryKey: ME_KEY });
      }}
    />
  );
}

function AllergyForm({
  initial,
  onSaved,
}: {
  initial: MyAllergens;
  onSaved: (data: MyAllergens) => void;
}) {
  const { t } = useTranslation();
  const errorMessage = useErrorMessage();
  const [consent, setConsent] = useState(initial.health_data_consent_at !== null);
  const [value, setValue] = useState<AllergyChoice[]>(
    initial.allergens.map((a) => ({ allergen_id: a.allergen_id, severity: a.severity })),
  );
  const save = useMutation({
    mutationFn: () =>
      consent
        ? apiPut<MyAllergens>('/me/allergens', { consent: true, allergens: value })
        : apiDelete<MyAllergens>('/me/health-consent'),
    onSuccess: onSaved,
  });
  return (
    <Card className="space-y-3">
      <h2 className="font-medium">{t('allergy.title')}</h2>
      {save.isError && <Alert>{errorMessage(save.error)}</Alert>}
      {save.isSuccess && <Alert tone="success">{t('common.saved')}</Alert>}
      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          className="mt-0.5 h-5 w-5"
          checked={consent}
          onChange={(e) => {
            setConsent(e.target.checked);
            if (!e.target.checked) setValue([]);
          }}
        />
        <span>{t('allergy.consent')}</span>
      </label>
      {!consent && initial.health_data_consent_at && (
        <Alert tone="warning">{t('allergy.revokeWarning')}</Alert>
      )}
      <AllergyEditor value={value} onChange={setValue} disabled={!consent} />
      <Button onClick={() => save.mutate()} disabled={save.isPending}>
        {t('common.save')}
      </Button>
    </Card>
  );
}
