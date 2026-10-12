import { useEffect, useRef } from 'react';

import { useAuthStore } from '@/features/auth/store';

export function wsUrl(path: string, token: string): string {
  const { protocol, host } = window.location;
  return `${protocol === 'https:' ? 'wss' : 'ws'}://${host}${path}?token=${encodeURIComponent(token)}`;
}

export interface SocketMessage {
  type: string;
  data: Record<string, unknown>;
}

/** A WebSocket to `path` with the access token; reconnects with backoff. `null` = off. */
export function useSocket(path: string | null, onMessage: (message: SocketMessage) => void) {
  const token = useAuthStore((s) => s.accessToken);
  const handler = useRef(onMessage);
  handler.current = onMessage;
  useEffect(() => {
    if (!path || !token || typeof WebSocket === 'undefined') return;
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let stopped = false;
    const connect = () => {
      socket = new WebSocket(wsUrl(path, token));
      socket.onopen = () => {
        attempt = 0;
      };
      socket.onmessage = (event) => {
        try {
          handler.current(JSON.parse(String(event.data)) as SocketMessage);
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
  }, [path, token]);
}
