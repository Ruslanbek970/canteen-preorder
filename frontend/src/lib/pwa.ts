import { useSyncExternalStore } from 'react';

/** One service worker for the offline cache and Web Push (public/sw.js). */
export const SW_URL = '/sw.js';
const MENU_CACHE = 'api-menu';

/** Registers the service worker in production builds; the dev server stays uncached. */
export function registerServiceWorker(): void {
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return;
  window.addEventListener('load', () => {
    void navigator.serviceWorker.register(SW_URL).catch(() => undefined);
  });
}

/** The cached menu carries the signed-in user's allergy marks: drop it on sign-out. */
export async function clearPersonalCache(): Promise<void> {
  if (typeof caches === 'undefined') return;
  await caches.delete(MENU_CACHE).catch(() => false);
}

function subscribe(callback: () => void): () => void {
  window.addEventListener('online', callback);
  window.addEventListener('offline', callback);
  return () => {
    window.removeEventListener('online', callback);
    window.removeEventListener('offline', callback);
  };
}

export function useOnline(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => navigator.onLine,
    () => true,
  );
}
