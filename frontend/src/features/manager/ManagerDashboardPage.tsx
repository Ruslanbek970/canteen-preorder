import { useTranslation } from 'react-i18next';

import { ManagerShell } from './ManagerShell';

export function ManagerDashboardPage() {
  const { t } = useTranslation();
  return (
    <ManagerShell title={t('pages.managerDashboard')}>
      <p className="text-slate-500">{t('app.comingSoon')}</p>
    </ManagerShell>
  );
}
