import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

export function HomePage() {
  const { t } = useTranslation();
  return (
    <section className="mx-auto max-w-xl p-4 text-center">
      <h1 className="mt-6 text-3xl font-semibold">{t('home.title')}</h1>
      <p className="mt-3 text-slate-600 dark:text-slate-300">{t('home.subtitle')}</p>
      <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
        <Link
          to="/login"
          className="rounded-lg bg-green-700 px-5 py-3 font-medium text-white hover:bg-green-800"
        >
          {t('auth.login')}
        </Link>
        <Link
          to="/register"
          className="rounded-lg border border-slate-300 px-5 py-3 font-medium hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-900"
        >
          {t('auth.register')}
        </Link>
      </div>
      <p className="mt-6 text-sm">
        <Link to="/c/main" className="text-green-700 underline dark:text-green-400">
          {t('home.publicMenu')}
        </Link>
      </p>
    </section>
  );
}
