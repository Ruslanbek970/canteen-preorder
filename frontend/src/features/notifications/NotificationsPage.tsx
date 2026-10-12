import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import type { AppNotification } from '@/api/types';
import { Button, EmptyState, ErrorState, LoadingState, PageTitle } from '@/components/ui';
import { formatDayTime } from '@/lib/format';

import { notificationLink, useMarkAllRead, useMarkRead, useNotifications } from './api';

export function NotificationsPage() {
  const { t } = useTranslation();
  const query = useNotifications();
  const readAll = useMarkAllRead();
  const unread = query.data?.unread ?? 0;
  return (
    <section className="mx-auto max-w-xl p-4">
      <PageTitle
        actions={
          unread > 0 && (
            <Button
              variant="secondary"
              disabled={readAll.isPending}
              onClick={() => readAll.mutate()}
            >
              {t('notifications.readAll')}
            </Button>
          )
        }
      >
        {t('notifications.title')}
      </PageTitle>
      {query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : query.data.items.length === 0 ? (
        <EmptyState>{t('notifications.empty')}</EmptyState>
      ) : (
        <ul className="space-y-2">
          {query.data.items.map((note) => (
            <NotificationRow key={note.id} note={note} />
          ))}
        </ul>
      )}
    </section>
  );
}

function NotificationRow({ note }: { note: AppNotification }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const markRead = useMarkRead();
  const link = notificationLink(note);
  const unread = note.read_at === null;
  const open = () => {
    if (unread) markRead.mutate(note.id);
    if (link) navigate(link);
  };
  return (
    <li>
      <button
        type="button"
        onClick={open}
        className={`w-full rounded-xl border p-3 text-left ${
          unread
            ? 'border-brand-300 border-l-4 border-l-brand-600 bg-white dark:border-brand-800 dark:bg-slate-900'
            : 'border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900'
        }`}
      >
        <div className="flex items-start justify-between gap-2">
          <p className={unread ? 'font-semibold' : 'font-medium'}>{note.title}</p>
          {unread && (
            <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-brand-700">
              <span className="sr-only">{t('notifications.unread')}</span>
            </span>
          )}
        </div>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{note.body}</p>
        <p className="mt-1 text-xs text-slate-500">{formatDayTime(note.sent_at)}</p>
      </button>
    </li>
  );
}
