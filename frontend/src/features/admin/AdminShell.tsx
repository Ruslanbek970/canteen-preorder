import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink } from 'react-router-dom';

const TABS = [
  { to: '/admin', labelKey: 'admin.tabs.users', end: true },
  { to: '/admin/canteens', labelKey: 'admin.tabs.canteens' },
  { to: '/admin/buildings', labelKey: 'admin.tabs.buildings' },
  { to: '/admin/groups', labelKey: 'admin.tabs.groups' },
  { to: '/admin/schedule', labelKey: 'admin.tabs.schedule' },
];

/** Section layout of the admin screens: a row of tabs and the page. */
export function AdminShell({ title, children }: { title: string; children: ReactNode }) {
  const { t } = useTranslation();
  return (
    <section className="p-4">
      <nav aria-label={t('admin.section')} className="-mx-4 mb-4 overflow-x-auto px-4">
        <ul className="flex gap-2">
          {TABS.map((tab) => (
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
      <h1 className="mb-4 text-2xl font-semibold">{title}</h1>
      {children}
    </section>
  );
}
