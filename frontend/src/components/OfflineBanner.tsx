import { useTranslation } from 'react-i18next';

import { useOnline } from '@/lib/pwa';

export function OfflineBanner() {
  const { t } = useTranslation();
  const online = useOnline();
  if (online) return null;
  return (
    <div
      role="status"
      className="bg-amber-100 px-4 py-2 text-center text-sm text-amber-900 dark:bg-amber-900 dark:text-amber-50"
    >
      {t('pwa.offline')}
    </div>
  );
}
