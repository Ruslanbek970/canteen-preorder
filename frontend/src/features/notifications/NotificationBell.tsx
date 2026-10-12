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
      className="relative rounded-lg p-2 text-white hover:bg-white/15"
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
        <span className="absolute -right-0.5 -top-0.5 min-w-[1.25rem] rounded-full bg-white px-1 text-center text-xs font-bold text-brand-700 ring-2 ring-brand-600">
          {unread > 99 ? '99+' : unread}
        </span>
      )}
    </Link>
  );
}
