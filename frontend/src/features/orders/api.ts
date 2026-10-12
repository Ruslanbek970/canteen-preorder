import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiGet, apiPost, qs } from '@/api/client';
import type { Order, OrderList, PaymentInfo, RepeatResponse, SlotsResponse } from '@/api/types';

export const ORDERS_KEY = ['orders'] as const;

export interface CreateOrderBody {
  canteen_id: number;
  pickup_slot_id: number;
  items: { menu_item_id: number; quantity: number }[];
  allergy_warning_ack: boolean;
}

export function useSlots(canteenId: number | null, date: string | null) {
  return useQuery({
    queryKey: ['slots', canteenId, date],
    queryFn: () => apiGet<SlotsResponse>(`/canteens/${canteenId}/slots${qs({ date })}`),
    enabled: Boolean(canteenId && date),
    refetchInterval: 30_000,
  });
}

export function useOrders() {
  return useQuery({ queryKey: ORDERS_KEY, queryFn: () => apiGet<OrderList>('/orders') });
}

export function useOrder(id: number) {
  return useQuery({
    queryKey: [...ORDERS_KEY, id],
    queryFn: () => apiGet<Order>(`/orders/${id}`),
    refetchInterval: 15_000,
  });
}

export function useCreateOrder() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateOrderBody) => apiPost<Order>('/orders', body),
    onSuccess: (order) => {
      client.setQueryData([...ORDERS_KEY, order.id], order);
      void client.invalidateQueries({ queryKey: ORDERS_KEY });
      void client.invalidateQueries({ queryKey: ['menu'] });
      void client.invalidateQueries({ queryKey: ['slots'] });
    },
    onError: () => {
      void client.invalidateQueries({ queryKey: ['menu'] });
      void client.invalidateQueries({ queryKey: ['slots'] });
    },
  });
}

export function useCancelOrder() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiPost<Order>(`/orders/${id}/cancel`),
    onSuccess: (order) => {
      client.setQueryData([...ORDERS_KEY, order.id], order);
      void client.invalidateQueries({ queryKey: ORDERS_KEY });
      void client.invalidateQueries({ queryKey: ['menu'] });
    },
  });
}

export function useRepeatOrder() {
  return useMutation({
    mutationFn: (id: number) => apiPost<RepeatResponse>(`/orders/${id}/repeat`),
  });
}

export function usePayOrder() {
  return useMutation({
    mutationFn: (id: number) => apiPost<PaymentInfo>(`/orders/${id}/pay`),
  });
}
