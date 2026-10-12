import { Link, Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { LanguageSwitcher } from '@/components/LanguageSwitcher';

export function Layout() {
  const { t } = useTranslation();
  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-slate-800">
        <Link to="/" className="font-semibold">
          {t('app.name')}
        </Link>
        <LanguageSwitcher />
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
