import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

const STEPS = ['order', 'slot', 'pickup'] as const;

export function HomePage() {
  const { t } = useTranslation();
  return (
    <section className="p-4">
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-600 to-brand-800 px-6 py-10 text-center text-white shadow-lg sm:py-14">
        <div
          className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/10"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -bottom-20 -left-10 h-48 w-48 rounded-full bg-white/10"
          aria-hidden
        />
        <h1 className="relative text-3xl font-bold tracking-tight sm:text-4xl">
          {t('home.title')}
        </h1>
        <p className="relative mx-auto mt-3 max-w-xl text-white">{t('home.subtitle')}</p>
        <div className="on-brand relative mt-7 flex flex-col gap-2 sm:flex-row sm:justify-center">
          <Link
            to="/login"
            className="rounded-xl bg-white px-6 py-3 font-semibold text-brand-700 shadow-sm hover:bg-brand-50"
          >
            {t('auth.login')}
          </Link>
          <Link
            to="/register"
            className="rounded-xl border-2 border-white/70 px-6 py-3 font-semibold text-white hover:bg-white/10"
          >
            {t('auth.register')}
          </Link>
        </div>
      </div>

      <ol className="mx-auto mt-6 grid max-w-4xl gap-3 sm:grid-cols-3">
        {STEPS.map((step, i) => (
          <li
            key={step}
            className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-600 font-bold text-white">
              {i + 1}
            </span>
            <h2 className="mt-3 font-semibold">{t(`home.steps.${step}.title`)}</h2>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
              {t(`home.steps.${step}.text`)}
            </p>
          </li>
        ))}
      </ol>

      <p className="mt-6 text-center text-sm">
        <Link to="/c/main" className="font-medium text-brand-700 underline dark:text-brand-300">
          {t('home.publicMenu')}
        </Link>
      </p>
    </section>
  );
}
