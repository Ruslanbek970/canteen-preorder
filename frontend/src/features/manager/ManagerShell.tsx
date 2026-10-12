import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink } from 'react-router-dom';

const MANAGER_TABS = [
  { to: '/manager', labelKey: 'manager.tabs.dashboard', end: true },
  { to: '/manager/reports', labelKey: 'manager.tabs.reports' },
  { to: '/manager/promotions', labelKey: 'manager.tabs.promotions' },
  { to: '/manager/menu', labelKey: 'manager.tabs.menu' },
  { to: '/manager/slots', labelKey: 'manager.tabs.slots' },
  { to: '/manager/dishes', labelKey: 'manager.tabs.dishes' },
  { to: '/manager/ingredients', labelKey: 'manager.tabs.ingredients' },
];

/** Section layout of the manager screens: a row of tabs and the page. */
export function ManagerShell({
  title,
  actions,
  children,
}: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <section className="p-4">
      <nav aria-label={t('manager.section')} className="-mx-4 mb-4 overflow-x-auto px-4">
        <ul className="flex gap-2">
          {MANAGER_TABS.map((tab) => (
            <li key={tab.to}>
              <NavLink
                to={tab.to}
                end={tab.end}
                className={({ isActive }) =>
                  `block whitespace-nowrap rounded-lg px-3 py-1.5 text-sm ${
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
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">{title}</h1>
        {actions}
      </div>
      {children}
    </section>
  );
}
