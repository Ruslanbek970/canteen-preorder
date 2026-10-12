import { useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';

import { apiGet, apiPost } from '@/api/client';
import type { Me } from '@/api/types';
import { Alert, Button, Card, Field, Input } from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';

import { needsOnboarding } from './onboarding';
import { useAuthStore } from './store';
import { ME_KEY, homeFor } from './useMe';

export function VerifyEmailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const errorMessage = useErrorMessage();
  const state = (useLocation().state ?? {}) as { email?: string };
  const [email, setEmail] = useState(state.email ?? '');
  const [code, setCode] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiPost('/auth/verify-email', { email: email.trim(), code: code.trim() });
      if (useAuthStore.getState().accessToken) {
        const me = await apiGet<Me>('/me');
        queryClient.setQueryData(ME_KEY, me);
        navigate(needsOnboarding(me) ? '/onboarding' : homeFor(me.role), { replace: true });
      } else {
        navigate('/login', { replace: true });
      }
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    setError(null);
    try {
      await apiPost('/auth/resend-code', { email: email.trim() });
      setInfo(t('auth.codeResent'));
    } catch (err) {
      setError(err);
    }
  }

  return (
    <section className="mx-auto max-w-sm p-4">
      <h1 className="mb-2 text-2xl font-semibold">{t('auth.verifyTitle')}</h1>
      <p className="mb-4 text-sm text-slate-500">{t('auth.verifyText')}</p>
      <Card>
        <form className="space-y-4" onSubmit={onSubmit}>
          {error !== null && <Alert>{errorMessage(error)}</Alert>}
          {info && <Alert tone="success">{info}</Alert>}
          <Field label={t('auth.email')}>
            <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label={t('auth.code')}>
            <Input
              inputMode="numeric"
              pattern="\d{6}"
              maxLength={6}
              required
              autoComplete="one-time-code"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              className="text-center text-2xl tracking-[0.5em]"
            />
          </Field>
          <Button type="submit" className="w-full" disabled={busy}>
            {t('auth.verify')}
          </Button>
          <Button
            variant="ghost"
            className="w-full"
            onClick={() => void resend()}
            disabled={!email}
          >
            {t('auth.resend')}
          </Button>
        </form>
      </Card>
    </section>
  );
}
