import { type FormEvent, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { Alert, Button, Card, Field, Input } from '@/components/ui';
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
    <section className="mx-auto max-w-sm p-4">
      <h1 className="mb-4 text-2xl font-semibold">{t('auth.loginTitle')}</h1>
      <Card>
        <form className="space-y-4" onSubmit={onSubmit}>
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
          <Button type="submit" className="w-full" disabled={busy}>
            {t('auth.login')}
          </Button>
        </form>
      </Card>
      <p className="mt-4 text-center text-sm">
        {t('auth.noAccount')}{' '}
        <Link className="text-brand-700 underline dark:text-brand-400" to="/register">
          {t('auth.register')}
        </Link>
      </p>
      <p className="mt-2 text-center text-xs text-slate-500">{t('auth.demoHint')}</p>
    </section>
  );
}
