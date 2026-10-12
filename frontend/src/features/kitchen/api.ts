import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiGet, apiPost } from '@/api/client';
import type {
  CloseDayResult,
  KitchenBoard,
  KitchenLabel,
  KitchenOrder,
  PrepSummary,
  WasteRecord,
} from '@/api/types';

export const KITCHEN_KEY = ['kitchen'] as const;

export function useBoard() {
  return useQuery({
    queryKey: [...KITCHEN_KEY, 'board'],
    queryFn: () => apiGet<KitchenBoard>('/kitchen/board'),
    refetchInterval: 60_000,
  });
}

export function usePrepSummary() {
  return useQuery({
    queryKey: [...KITCHEN_KEY, 'prep'],
    queryFn: () => apiGet<PrepSummary>('/kitchen/prep-summary'),
    refetchInterval: 60_000,
  });
}

function useKitchenMutation<T, A>(fn: (arg: A) => Promise<T>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSettled: () => void client.invalidateQueries({ queryKey: KITCHEN_KEY }),
  });
}

export const useSetStatus = () =>
  useKitchenMutation(({ id, status }: { id: number; status: 'cooking' | 'ready' }) =>
    apiPost<KitchenOrder>(`/kitchen/orders/${id}/status`, { status }),
  );

export const useStartSlot = () =>
  useKitchenMutation((slotId: number) =>
    apiPost<{ slot_id: number; order_ids: number[] }>(`/kitchen/slots/${slotId}/start`),
  );

export const useCloseDay = () =>
  useKitchenMutation(() => apiPost<CloseDayResult>('/kitchen/close-day'));

export const useRecordWaste = () =>
  useKitchenMutation((body: { menu_item_id: number; portions: number; reason: string }) =>
    apiPost<WasteRecord>('/kitchen/waste', body),
  );

export function useWaste() {
  return useQuery({
    queryKey: [...KITCHEN_KEY, 'waste'],
    queryFn: () => apiGet<WasteRecord[]>('/kitchen/waste'),
  });
}

export function useLabels(ids: number[]) {
  return useQuery({
    queryKey: [...KITCHEN_KEY, 'labels', ids],
    queryFn: () =>
      Promise.all(ids.map((id) => apiGet<KitchenLabel>(`/kitchen/orders/${id}/label`))),
    enabled: ids.length > 0,
  });
}
