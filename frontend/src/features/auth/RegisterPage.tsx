import { useQuery } from '@tanstack/react-query';
import { type FormEvent, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';

import { apiGet, apiPost } from '@/api/client';
import type { Group, Language } from '@/api/types';
import { Alert, Button, Field, Input, Select, Spinner } from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';

import { useLogin } from './useMe';

export function RegisterPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const login = useLogin();
  const errorMessage = useErrorMessage();
  const groups = useQuery({ queryKey: ['groups'], queryFn: () => apiGet<Group[]>('/groups') });
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    role: 'student' as 'student' | 'teacher',
    group_id: '',
  });
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const set = (key: keyof typeof form) => (value: string) =>
    setForm((f) => ({ ...f, [key]: value }));

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiPost('/auth/register', {
        full_name: form.full_name,
        email: form.email.trim(),
        password: form.password,
        role: form.role,
        group_id: form.role === 'student' && form.group_id ? Number(form.group_id) : null,
        preferred_language: (i18n.resolvedLanguage ?? 'ru') as Language,
      });
      await login(form.email.trim(), form.password);
      navigate('/verify', { state: { email: form.email.trim() } });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-sm">
      <h1 className="text-3xl font-bold tracking-tight">{t('auth.registerTitle')}</h1>
      <p className="mt-1 text-slate-600">{t('auth.registerSubtitle')}</p>
      <form className="mt-6 space-y-3" onSubmit={onSubmit}>
        {error !== null && <Alert>{errorMessage(error)}</Alert>}
        <Field label={t('auth.fullName')}>
          <Input
            required
            value={form.full_name}
            onChange={(e) => set('full_name')(e.target.value)}
          />
        </Field>
        <Field label={t('auth.email')} hint={t('auth.emailHint')}>
          <Input
            type="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={(e) => set('email')(e.target.value)}
          />
        </Field>
        <Field label={t('auth.password')} hint={t('auth.passwordHint')}>
          <Input
            type="password"
            autoComplete="new-password"
            minLength={8}
            required
            value={form.password}
            onChange={(e) => set('password')(e.target.value)}
          />
        </Field>
        <Field label={t('auth.role')}>
          <Select value={form.role} onChange={(e) => set('role')(e.target.value)}>
            <option value="student">{t('roles.studentRole')}</option>
            <option value="teacher">{t('roles.teacherRole')}</option>
          </Select>
        </Field>
        {form.role === 'student' && (
          <Field label={t('auth.group')}>
            <Select
              required
              value={form.group_id}
              onChange={(e) => set('group_id')(e.target.value)}
            >
              <option value="">{t('auth.chooseGroup')}</option>
              {groups.data?.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.code}
                </option>
              ))}
            </Select>
          </Field>
        )}
        <Button
          type="submit"
          className="!mt-5 w-full !rounded-full uppercase tracking-wider"
          disabled={busy}
        >
          {busy && <Spinner light />}
          {t('auth.register')}
        </Button>
      </form>
      <p className="mt-5 text-center text-sm md:hidden">
        {t('auth.haveAccount')}{' '}
        <Link className="font-medium text-brand-700 underline" to="/login">
          {t('auth.login')}
        </Link>
      </p>
    </div>
  );
}
