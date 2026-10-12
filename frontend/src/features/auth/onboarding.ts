import type { Me } from '@/api/types';

const KEY = 'canteen-onboarded';

function done(): number[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '[]') as number[];
  } catch {
    return [];
  }
}

/** Onboarding (SPEC 7.1) is shown once per account on this device, only to customers. */
export function needsOnboarding(me: Me): boolean {
  return (me.role === 'student' || me.role === 'teacher') && !done().includes(me.id);
}

export function markOnboarded(userId: number): void {
  localStorage.setItem(KEY, JSON.stringify([...new Set([...done(), userId])]));
}
