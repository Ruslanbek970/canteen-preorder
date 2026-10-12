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
                    isActive ? 'bg-green-600 text-white' : 'bg-slate-100 dark:bg-slate-800'
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
