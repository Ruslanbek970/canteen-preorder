import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

const SECTIONS = [
  { to: '/menu', labelKey: 'roles.student' },
  { to: '/kitchen', labelKey: 'roles.kitchen' },
  { to: '/pickup', labelKey: 'roles.cashier' },
  { to: '/manager', labelKey: 'roles.manager' },
  { to: '/admin', labelKey: 'roles.admin' },
] as const;

export function HomePage() {
  const { t } = useTranslation();
  return (
    <section className="mx-auto max-w-3xl p-4">
      <h1 className="text-2xl font-semibold">{t('home.title')}</h1>
      <p className="mt-2 text-slate-500 dark:text-slate-400">{t('home.subtitle')}</p>
      <ul className="mt-4 grid gap-2 sm:grid-cols-2">
        {SECTIONS.map((s) => (
          <li key={s.to}>
            <Link
              to={s.to}
              className="block rounded-lg border border-slate-200 p-4 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-900"
            >
              {t(s.labelKey)}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
