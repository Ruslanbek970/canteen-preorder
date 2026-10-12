import { useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';

import { useAuthStore } from '@/features/auth/store';

import { ORDERS_KEY } from './api';

export function wsUrl(path: string, token: string): string {
  const { protocol, host } = window.location;
  return `${protocol === 'https:' ? 'wss' : 'ws'}://${host}${path}?token=${encodeURIComponent(token)}`;
}

/** `/ws/me`: refreshes my orders when their status changes; reconnects with backoff. */
export function useLiveOrders(enabled: boolean) {
  const token = useAuthStore((s) => s.accessToken);
  const client = useQueryClient();
  useEffect(() => {
    if (!enabled || !token || typeof WebSocket === 'undefined') return;
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let stopped = false;
    const connect = () => {
      socket = new WebSocket(wsUrl('/ws/me', token));
      socket.onopen = () => {
        attempt = 0;
      };
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(String(event.data)) as { type: string };
          if (message.type.startsWith('order.') || message.type.startsWith('payment.')) {
            void client.invalidateQueries({ queryKey: ORDERS_KEY });
          }
        } catch {
          // ignore malformed frames
        }
      };
      socket.onclose = () => {
        if (stopped) return;
        attempt += 1;
        timer = setTimeout(connect, Math.min(30_000, 1000 * 2 ** attempt));
      };
    };
    connect();
    return () => {
      stopped = true;
      clearTimeout(timer);
      socket?.close();
    };
  }, [enabled, token, client]);
}
