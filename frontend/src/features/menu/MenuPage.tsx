import { useTranslation } from 'react-i18next';

import { Alert, EmptyState, LoadingState, PageTitle, Select } from '@/components/ui';
import { useMe } from '@/features/auth/useMe';

import { MenuView } from './MenuView';
import { useCanteen } from './useCanteen';

export function MenuPage() {
  const { t } = useTranslation();
  const me = useMe();
  const { canteens, list, current, select } = useCanteen();
  if (canteens.isPending) return <LoadingState />;
  if (!current) return <EmptyState>{t('menu.noCanteens')}</EmptyState>;
  return (
    <section className="p-4">
      <PageTitle
        actions={
          list.length > 1 ? (
            <Select
              aria-label={t('menu.canteen')}
              className="w-auto"
              value={current.id}
              onChange={(e) => select(Number(e.target.value))}
            >
              {list.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          ) : (
            <span className="text-sm text-slate-500">{current.name}</span>
          )
        }
      >
        {t('pages.menu')}
      </PageTitle>
      {me.data && !me.data.email_verified && (
        <div className="mb-3">
          <Alert tone="warning">{t('menu.verifyToOrder')}</Alert>
        </div>
      )}
      <MenuView canteenId={current.id} signedIn />
    </section>
  );
}
