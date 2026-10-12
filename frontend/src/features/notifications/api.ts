import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiGet, apiPost } from '@/api/client';
import type { AppNotification, NotificationList } from '@/api/types';

export const NOTIFICATIONS_KEY = ['notifications'] as const;

export function useNotifications(enabled = true) {
  return useQuery({
    queryKey: NOTIFICATIONS_KEY,
    queryFn: () => apiGet<NotificationList>('/notifications'),
    enabled,
    refetchInterval: 60_000,
  });
}

export function useMarkRead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiPost<AppNotification>(`/notifications/${id}/read`),
    onSuccess: () => void client.invalidateQueries({ queryKey: NOTIFICATIONS_KEY }),
  });
}

export function useMarkAllRead() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<{ marked: number }>('/notifications/read-all'),
    onSuccess: () => void client.invalidateQueries({ queryKey: NOTIFICATIONS_KEY }),
  });
}

/** Where a notification leads: its order, the menu for a discount, or nowhere. */
export function notificationLink(note: AppNotification): string | null {
  if (note.order_id) return `/orders/${note.order_id}`;
  if (note.promotion_id) return '/menu';
  return null;
}
