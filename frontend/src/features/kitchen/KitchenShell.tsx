import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink } from 'react-router-dom';

const TABS = [
  { to: '/kitchen', labelKey: 'kitchen.tabs.board', end: true },
  { to: '/kitchen/waste', labelKey: 'kitchen.tabs.waste' },
];

export function KitchenShell({ actions, children }: { actions?: ReactNode; children: ReactNode }) {
  const { t } = useTranslation();
  return (
    <section className="p-4 text-lg">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <nav aria-label={t('kitchen.section')}>
          <ul className="flex gap-2">
            {TABS.map((tab) => (
              <li key={tab.to}>
                <NavLink
                  to={tab.to}
                  end={tab.end}
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
        {actions}
      </div>
      {children}
    </section>
  );
}
