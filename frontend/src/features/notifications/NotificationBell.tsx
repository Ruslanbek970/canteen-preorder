import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { useNotifications } from './api';

/** The bell in the header with the number of unread notifications. */
export function NotificationBell() {
  const { t } = useTranslation();
  const query = useNotifications();
  const unread = query.data?.unread ?? 0;
  return (
    <Link
      to="/notifications"
      className="relative rounded p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
      aria-label={
        unread > 0 ? t('notifications.bellUnread', { count: unread }) : t('notifications.title')
      }
    >
      <svg
        viewBox="0 0 24 24"
        className="h-5 w-5"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.7 21a2 2 0 0 1-3.4 0" />
      </svg>
      {unread > 0 && (
        <span className="absolute -right-0.5 -top-0.5 min-w-[1.25rem] rounded-full bg-red-600 px-1 text-center text-xs font-medium text-white">
          {unread > 99 ? '99+' : unread}
        </span>
      )}
    </Link>
  );
}
