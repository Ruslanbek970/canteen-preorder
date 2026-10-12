import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink } from 'react-router-dom';

const TABS = [
  { to: '/pickup', labelKey: 'nav.pickup' },
  { to: '/pos', labelKey: 'nav.pos' },
];

export function PickupShell({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  return (
    <section className="p-4 text-lg">
      <nav aria-label={t('pickup.section')} className="mb-4">
        <ul className="flex gap-2">
          {TABS.map((tab) => (
            <li key={tab.to}>
              <NavLink
                to={tab.to}
                className={({ isActive }) =>
                  `block rounded-lg px-4 py-2 ${
                    isActive
                      ? 'bg-brand-600 font-medium text-white shadow-sm'
                      : 'border border-slate-200 bg-white text-slate-700 hover:border-brand-300 hover:text-brand-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200'
                  }`
                }
              >
                {t(tab.labelKey)}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      {children}
    </section>
  );
}
