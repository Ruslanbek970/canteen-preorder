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
                      isActive ? 'bg-green-700 text-white' : 'bg-slate-100 dark:bg-slate-800'
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
