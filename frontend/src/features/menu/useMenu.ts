import { useQuery } from '@tanstack/react-query';

import { apiGet, qs } from '@/api/client';
import type { MenuResponse } from '@/api/types';
import { useAuthStore } from '@/features/auth/store';

export function useMenu(canteenId: number | null | undefined, date?: string) {
  const signedIn = useAuthStore((s) => Boolean(s.accessToken));
  return useQuery({
    queryKey: ['menu', canteenId, date ?? 'today', signedIn],
    queryFn: () => apiGet<MenuResponse>(`/canteens/${canteenId}/menu${qs({ date })}`),
    enabled: Boolean(canteenId),
    refetchInterval: 60_000,
  });
}
