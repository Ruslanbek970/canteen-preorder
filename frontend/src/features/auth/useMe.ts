import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';

import { apiGet, apiPost } from '@/api/client';
import type { Me, Role, TokenPair } from '@/api/types';
import i18n from '@/i18n';
import { clearPersonalCache } from '@/lib/pwa';

import { useAuthStore } from './store';

export const ME_KEY = ['me'] as const;

export function useMe() {
  const token = useAuthStore((s) => s.accessToken);
  return useQuery({
    queryKey: ME_KEY,
    queryFn: () => apiGet<Me>('/me'),
    enabled: Boolean(token),
    staleTime: 60_000,
  });
}

/** Start page of every role after sign-in (SPEC 16, phase 1). */
export function homeFor(role: Role): string {
  switch (role) {
    case 'student':
    case 'teacher':
      return '/menu';
    case 'cook':
      return '/kitchen';
    case 'cashier':
      return '/pickup';
    case 'canteen_manager':
      return '/manager';
    case 'admin':
      return '/admin';
  }
}

export function useLogin() {
  const queryClient = useQueryClient();
  const setTokens = useAuthStore((s) => s.setTokens);
  return useCallback(
    async (email: string, password: string): Promise<Me> => {
      const tokens = await apiPost<TokenPair>('/auth/login', { email, password });
      setTokens(tokens.access_token, tokens.refresh_token);
      const me = await apiGet<Me>('/me');
      queryClient.setQueryData(ME_KEY, me);
      if (me.preferred_language !== i18n.resolvedLanguage) {
        void i18n.changeLanguage(me.preferred_language);
      }
      return me;
    },
    [queryClient, setTokens],
  );
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useCallback(async () => {
    const { refreshToken, clear } = useAuthStore.getState();
    if (refreshToken) {
      await apiPost('/auth/logout', { refresh_token: refreshToken }).catch(() => undefined);
    }
    clear();
    queryClient.clear();
    await clearPersonalCache();
  }, [queryClient]);
}
