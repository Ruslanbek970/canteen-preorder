import { useQuery } from '@tanstack/react-query';
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import { apiGet } from '@/api/client';
import type { Canteen } from '@/api/types';

const useSelected = create<{ id: number | null; set: (id: number) => void }>()(
  persist((set) => ({ id: null, set: (id) => set({ id }) }), { name: 'canteen-selected' }),
);

/** Canteens list and the one the customer picked (the first one by default). */
export function useCanteen() {
  const canteens = useQuery({
    queryKey: ['canteens'],
    queryFn: () => apiGet<Canteen[]>('/canteens'),
    staleTime: 5 * 60_000,
  });
  const selectedId = useSelected((s) => s.id);
  const select = useSelected((s) => s.set);
  const list = canteens.data ?? [];
  const current = list.find((c) => c.id === selectedId) ?? list[0] ?? null;
  return { canteens, list, current, select };
}
