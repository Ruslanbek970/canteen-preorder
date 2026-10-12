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

/** `2026-10-13` → `13.10` (a calendar date, no time zone shift). */
export function formatDay(isoDate: string): string {
  const [, m, d] = isoDate.split('-');
  return `${d}.${m}`;
}

/** `12:00:00` → `12:00`. */
export function formatClock(time: string): string {
  return time.slice(0, 5);
}

/** Today's calendar date in the canteen time zone, `YYYY-MM-DD`. */
export function todayLocal(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: APP_TIME_ZONE }).format(now);
}

/** Adds days to a `YYYY-MM-DD` date. */
export function addDays(isoDate: string, days: number): string {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** Formats an ISO timestamp as `13.10 12:30` in the canteen time zone. */
export function formatDayTime(iso: string | Date): string {
  const date = typeof iso === 'string' ? new Date(iso) : iso;
  return `${formatDay(todayLocal(date))} ${formatTime(date)}`;
}
