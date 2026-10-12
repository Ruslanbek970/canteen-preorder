import { useTranslation } from 'react-i18next';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';

import { LanguageSwitcher } from '@/components/LanguageSwitcher';
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
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-2 px-4 py-2">
          <Link to="/" className="truncate font-semibold text-green-700 dark:text-green-400">
            {t('app.name')}
          </Link>
          <div className="flex items-center gap-2">
            <LanguageSwitcher />
            {token && customer && <NotificationBell />}
            {token && me.data ? (
              <button
                type="button"
                className="rounded px-2 py-1 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                onClick={() => void logout().then(() => navigate('/login'))}
              >
                {t('auth.logout')}
              </button>
            ) : (
              <Link
                to="/login"
                className="rounded px-2 py-1 text-sm text-green-700 dark:text-green-400"
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
                      `block whitespace-nowrap border-b-2 px-3 py-2 text-sm ${
                        isActive
                          ? 'border-green-600 font-medium text-green-700 dark:text-green-400'
                          : 'border-transparent text-slate-600 dark:text-slate-300'
                      }`
                    }
                  >
                    {t(item.labelKey)}
                    {item.to === '/cart' && inCart > 0 && (
                      <span className="ml-1 rounded-full bg-green-600 px-1.5 text-xs text-white">
                        {inCart}
                      </span>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        )}
      </header>
      <main id="main" className="mx-auto w-full max-w-6xl flex-1">
        <Outlet />
      </main>
    </div>
  );
}
