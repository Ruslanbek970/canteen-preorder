import { useTranslation } from 'react-i18next';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';

import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { OfflineBanner } from '@/components/OfflineBanner';
import { useAuthStore } from '@/features/auth/store';
import { useLogout, useMe } from '@/features/auth/useMe';
import { cartCount, useCartStore } from '@/features/cart/store';
import { NotificationBell } from '@/features/notifications/NotificationBell';
import { useLiveOrders } from '@/features/orders/useLiveOrders';

import { NAV } from './nav';

export function Layout() {
  const { t } = useTranslation();
  const token = useAuthStore((s) => s.accessToken);
  const me = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  const items = token && me.data ? NAV[me.data.role] : [];
  const inCart = useCartStore((s) => cartCount(s.lines));
  const customer = me.data?.role === 'student' || me.data?.role === 'teacher';
  useLiveOrders(Boolean(token) && customer);

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:p-2">
        {t('nav.skipToContent')}
      </a>
      <header className="on-brand sticky top-0 z-20 bg-brand-600 text-white shadow-md dark:bg-brand-800">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-2 px-4 py-2.5">
          <Link to="/" className="flex min-w-0 items-center gap-2 font-bold tracking-tight">
            <BrandMark />
            <span className="truncate">{t('app.name')}</span>
          </Link>
          <div className="flex items-center gap-1 sm:gap-2">
            <LanguageSwitcher />
            {token && customer && <NotificationBell />}
            {token && me.data ? (
              <button
                type="button"
                className="rounded-lg px-2 py-1.5 text-sm font-medium text-white/90 hover:bg-white/15 hover:text-white"
                onClick={() => void logout().then(() => navigate('/login'))}
              >
                {t('auth.logout')}
              </button>
            ) : (
              <Link
                to="/login"
                className="rounded-lg bg-white px-3 py-1.5 text-sm font-semibold text-brand-700 hover:bg-brand-50"
              >
                {t('auth.login')}
              </Link>
            )}
          </div>
        </div>
        {items.length > 0 && (
          <nav aria-label={t('nav.main')} className="mx-auto max-w-6xl overflow-x-auto px-2">
            <ul className="flex gap-1">
              {items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    className={({ isActive }) =>
                      `block whitespace-nowrap border-b-[3px] px-3 py-2 text-sm ${
                        isActive
                          ? 'border-white font-semibold text-white'
                          : 'border-transparent text-white/85 hover:border-white/40 hover:text-white'
                      }`
                    }
                  >
                    {t(item.labelKey)}
                    {item.to === '/cart' && inCart > 0 && (
                      <span className="ml-1 rounded-full bg-white px-1.5 text-xs font-bold text-brand-700">
                        {inCart}
                      </span>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        )}
        <OfflineBanner />
      </header>
      <main id="main" className="mx-auto w-full max-w-6xl flex-1">
        <Outlet />
      </main>
    </div>
  );
}

/** The app icon (plate, fork and knife) as a white badge on the red header. */
function BrandMark() {
  return (
    <span
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-brand-600"
      aria-hidden
    >
      <svg viewBox="0 0 512 512" className="h-6 w-6" fill="none" stroke="currentColor">
        <circle cx="256" cy="268" r="120" strokeWidth={36} />
        <circle cx="256" cy="268" r="56" fill="currentColor" stroke="none" />
        <path
          d="M112 120v84M88 120v56a24 24 0 0 0 48 0v-56M112 204v196"
          strokeWidth={28}
          strokeLinecap="round"
        />
        <path
          d="M400 120c-28 16-32 70-32 100h32v180"
          strokeWidth={28}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}
