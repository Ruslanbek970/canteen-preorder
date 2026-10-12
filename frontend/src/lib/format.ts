export const APP_TIME_ZONE = 'Asia/Almaty';

const NBSP = String.fromCharCode(0xa0);

/** Formats an amount in tenge as `1 500 ₸` (rounded to whole tenge). Accepts API decimal strings. */
export function formatPrice(amount: number | string): string {
  const value = Math.round(typeof amount === 'string' ? Number(amount) : amount);
  const digits = Math.abs(value)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
  return `${value < 0 ? '-' : ''}${digits}${NBSP}₸`;
}

/** Formats an ISO timestamp as `HH:mm` in the canteen time zone. */
export function formatTime(iso: string | Date): string {
  const date = typeof iso === 'string' ? new Date(iso) : iso;
  return new Intl.DateTimeFormat('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: APP_TIME_ZONE,
  }).format(date);
}
