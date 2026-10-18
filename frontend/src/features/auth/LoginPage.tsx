import { type FormEvent, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { Alert, Button, Field, Input, Spinner } from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';

import { homeFor, useLogin } from './useMe';
import { needsOnboarding } from './onboarding';

export function LoginPage() {
  const { t } = useTranslation();
  const login = useLogin();
  const navigate = useNavigate();
  const location = useLocation();
  const errorMessage = useErrorMessage();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const me = await login(email.trim(), password);
      const from = (location.state as { from?: string } | null)?.from;
      if (!me.email_verified) navigate('/verify', { state: { email: me.email } });
      else if (needsOnboarding(me)) navigate('/onboarding');
      else navigate(from && from !== '/login' ? from : homeFor(me.role), { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-sm">
      <h1 className="text-3xl font-bold tracking-tight">{t('auth.loginTitle')}</h1>
      <p className="mt-1 text-slate-600">{t('auth.loginSubtitle')}</p>
      <form className="mt-6 space-y-4" onSubmit={onSubmit}>
        {error !== null && <Alert>{errorMessage(error)}</Alert>}
        <Field label={t('auth.email')}>
          <Input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        <Field label={t('auth.password')}>
          <Input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        <Button
          type="submit"
          className="w-full !rounded-full uppercase tracking-wider"
          disabled={busy}
        >
          {busy && <Spinner light />}
          {t('auth.login')}
        </Button>
      </form>
      <p className="mt-5 text-center text-sm md:hidden">
        {t('auth.noAccount')}{' '}
        <Link className="font-medium text-brand-700 underline" to="/register">
          {t('auth.register')}
        </Link>
      </p>
      <p className="mt-6 rounded-xl bg-slate-50 p-3 text-xs leading-relaxed text-slate-600 ring-1 ring-slate-200">
        {t('auth.demoHint')}
      </p>
    </div>
  );
}
