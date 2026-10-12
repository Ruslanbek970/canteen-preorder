import { useQuery } from '@tanstack/react-query';

import { apiGet } from '@/api/client';
import type { AdminCanteen, AdminGroup, Building } from '@/api/types';

export const ADMIN_KEY = ['admin'] as const;

export function useAdminCanteens() {
  return useQuery({
    queryKey: [...ADMIN_KEY, 'canteens'],
    queryFn: () => apiGet<AdminCanteen[]>('/admin/canteens'),
  });
}

export function useBuildings() {
  return useQuery({
    queryKey: [...ADMIN_KEY, 'buildings'],
    queryFn: () => apiGet<Building[]>('/admin/buildings'),
  });
}

export function useAdminGroups() {
  return useQuery({
    queryKey: [...ADMIN_KEY, 'groups'],
    queryFn: () => apiGet<AdminGroup[]>('/admin/groups'),
  });
}
