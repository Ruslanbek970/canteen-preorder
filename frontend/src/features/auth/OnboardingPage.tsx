import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { apiGet, apiPatch, apiPut } from '@/api/client';
import type { Group, Language, Me } from '@/api/types';
import { Alert, Button, Card, Field, LoadingState, Select } from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';
import { SUPPORTED_LANGUAGES } from '@/i18n';
import { AllergyEditor, type AllergyChoice } from '@/features/profile/AllergyEditor';

import { markOnboarded } from './onboarding';
import { ME_KEY, homeFor, useMe } from './useMe';

const LANGUAGE_NAMES: Record<Language, string> = { ru: 'Русский', kk: 'Қазақша', en: 'English' };

export function OnboardingPage() {
  const me = useMe();
  if (!me.data) return <LoadingState />;
  return <OnboardingForm me={me.data} key={me.data.id} />;
}

function OnboardingForm({ me }: { me: Me }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const groups = useQuery({ queryKey: ['groups'], queryFn: () => apiGet<Group[]>('/groups') });
  const [groupId, setGroupId] = useState(me.group_id ? String(me.group_id) : '');
  const [language, setLanguage] = useState<Language>(
    (i18n.resolvedLanguage as Language | undefined) ?? me.preferred_language,
  );
  const [consent, setConsent] = useState(false);
  const [allergies, setAllergies] = useState<AllergyChoice[]>([]);

  const finish = () => {
    markOnboarded(me.id);
    navigate(homeFor(me.role), { replace: true });
  };

  const save = useMutation({
    mutationFn: async () => {
      const patch: Record<string, unknown> = { preferred_language: language };
      if (me.role === 'student' && groupId) patch.group_id = Number(groupId);
      await apiPatch<Me>('/me', patch);
      if (consent) await apiPut('/me/allergens', { consent: true, allergens: allergies });
    },
    onSuccess: async () => {
      await i18n.changeLanguage(language);
      await queryClient.invalidateQueries({ queryKey: ME_KEY });
      finish();
    },
  });

  return (
    <section className="mx-auto max-w-md p-4">
      <h1 className="mb-1 text-2xl font-semibold">{t('onboarding.title')}</h1>
      <p className="mb-4 text-sm text-slate-500">{t('onboarding.subtitle')}</p>
      <Card className="space-y-5">
        {save.isError && <Alert>{errorMessage(save.error)}</Alert>}
        {me.role === 'student' && (
          <Field label={t('auth.group')}>
            <Select value={groupId} onChange={(e) => setGroupId(e.target.value)}>
              {groups.data?.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.code}
                </option>
              ))}
            </Select>
          </Field>
        )}
        <Field label={t('nav.language')}>
          <Select value={language} onChange={(e) => setLanguage(e.target.value as Language)}>
            {SUPPORTED_LANGUAGES.map((l) => (
              <option key={l} value={l}>
                {LANGUAGE_NAMES[l]}
              </option>
            ))}
          </Select>
        </Field>
        <div>
          <h2 className="mb-1 font-medium">{t('allergy.title')}</h2>
          <label className="mb-2 flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              className="mt-0.5 h-5 w-5"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
            />
            <span>{t('allergy.consent')}</span>
          </label>
          <AllergyEditor value={allergies} onChange={setAllergies} disabled={!consent} />
        </div>
        <div className="flex gap-2">
          <Button className="flex-1" onClick={() => save.mutate()} disabled={save.isPending}>
            {t('common.save')}
          </Button>
          <Button variant="secondary" onClick={finish}>
            {t('common.skip')}
          </Button>
        </div>
      </Card>
    </section>
  );
}
