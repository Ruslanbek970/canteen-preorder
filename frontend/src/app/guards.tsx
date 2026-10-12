import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import type { Role } from '@/api/types';
import { ErrorState, LoadingState } from '@/components/ui';
import { useAuthStore } from '@/features/auth/store';
import { homeFor, useMe } from '@/features/auth/useMe';

/** Renders children only for signed-in users with one of `roles` (all roles if omitted). */
export function RequireRole({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const token = useAuthStore((s) => s.accessToken);
  const location = useLocation();
  const me = useMe();
  if (!token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (me.isPending) return <LoadingState />;
  if (me.isError) {
    if (!useAuthStore.getState().accessToken) return <Navigate to="/login" replace />;
    return <ErrorState error={me.error} onRetry={() => void me.refetch()} />;
  }
  if (roles && !roles.includes(me.data.role)) {
    return <Navigate to={homeFor(me.data.role)} replace />;
  }
  return <>{children}</>;
}

/** Sends signed-in users from `/` and `/login` to their start page. */
export function RedirectIfSignedIn({ children }: { children: ReactNode }) {
  const token = useAuthStore((s) => s.accessToken);
  const me = useMe();
  if (token && me.data) return <Navigate to={homeFor(me.data.role)} replace />;
  if (token && me.isPending) return <LoadingState />;
  return <>{children}</>;
}
