import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';

import { apiGet } from '@/api/client';
import type { Canteen } from '@/api/types';
import { ErrorState, LoadingState, PageTitle } from '@/components/ui';
import { useAuthStore } from '@/features/auth/store';
import { formatClock } from '@/lib/format';

import { MenuView } from './MenuView';

/** What the QR poster at the entrance opens: the menu without signing in (SPEC 9.1, item 12). */
export function PublicCanteenPage() {
  const { t } = useTranslation();
  const { slug = '' } = useParams();
  const signedIn = useAuthStore((s) => Boolean(s.accessToken));
  const canteen = useQuery({
    queryKey: ['canteen', slug],
    queryFn: () => apiGet<Canteen>(`/canteens/by-slug/${encodeURIComponent(slug)}`),
  });
  if (canteen.isPending) return <LoadingState />;
  if (canteen.isError) return <ErrorState error={canteen.error} />;
  return (
    <section className="p-4">
      <PageTitle
        actions={
          <Link
            to={signedIn ? '/menu' : '/login'}
            state={{ from: '/menu' }}
            className="rounded-lg bg-green-600 px-4 py-2 font-medium text-white hover:bg-green-700"
          >
            {signedIn ? t('menu.goOrder') : t('menu.loginToOrder')}
          </Link>
        }
      >
        {canteen.data.name}
      </PageTitle>
      <p className="-mt-2 mb-4 text-sm text-slate-500">
        {t('menu.hours', {
          from: formatClock(canteen.data.opens_at),
          to: formatClock(canteen.data.closes_at),
        })}
      </p>
      <MenuView canteenId={canteen.data.id} signedIn={false} />
    </section>
  );
}
