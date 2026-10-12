import { useQueryClient } from '@tanstack/react-query';

import { useSocket } from '@/lib/socket';

import { NOTIFICATIONS_KEY } from '@/features/notifications/api';

import { ORDERS_KEY } from './api';

/** `/ws/me`: refreshes my orders when their status changes, and my notifications. */
export function useLiveOrders(enabled: boolean) {
  const client = useQueryClient();
  useSocket(enabled ? '/ws/me' : null, (message) => {
    if (message.type.startsWith('order.') || message.type.startsWith('payment.')) {
      void client.invalidateQueries({ queryKey: ORDERS_KEY });
    }
    if (message.type.startsWith('notification.')) {
      void client.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
    }
  });
}
