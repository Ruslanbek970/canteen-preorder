import type { ReactElement } from 'react';
import type { RouteObject } from 'react-router-dom';

import type { Role } from '@/api/types';

import { PlaceholderPage } from '@/components/PlaceholderPage';
import { AdminPage } from '@/features/admin/AdminPage';
import { LoginPage } from '@/features/auth/LoginPage';
import { OnboardingPage } from '@/features/auth/OnboardingPage';
import { RegisterPage } from '@/features/auth/RegisterPage';
import { VerifyEmailPage } from '@/features/auth/VerifyEmailPage';
import { KitchenPage } from '@/features/kitchen/KitchenPage';
import { ManagerDashboardPage } from '@/features/manager/ManagerDashboardPage';
import { MenuPage } from '@/features/menu/MenuPage';
import { PublicCanteenPage } from '@/features/menu/PublicCanteenPage';
import { OrdersPage } from '@/features/orders/OrdersPage';
import { PickupPage } from '@/features/pickup/PickupPage';
import { PosPage } from '@/features/pos/PosPage';
import { ProfilePage } from '@/features/profile/ProfilePage';

import { RedirectIfSignedIn, RequireRole } from './guards';
import { HomePage } from './HomePage';
import { Layout } from './Layout';
import { ADMIN, CUSTOMER, KITCHEN, MANAGER, PICKUP } from './roles';

const guard = (element: ReactElement, roles?: Role[]) => (
  <RequireRole roles={roles}>{element}</RequireRole>
);

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      {
        index: true,
        element: (
          <RedirectIfSignedIn>
            <HomePage />
          </RedirectIfSignedIn>
        ),
      },
      {
        path: 'login',
        element: (
          <RedirectIfSignedIn>
            <LoginPage />
          </RedirectIfSignedIn>
        ),
      },
      { path: 'register', element: <RegisterPage /> },
      { path: 'verify', element: <VerifyEmailPage /> },
      { path: 'c/:slug', element: <PublicCanteenPage /> },
      { path: 'onboarding', element: guard(<OnboardingPage />, CUSTOMER) },
      { path: 'profile', element: guard(<ProfilePage />) },
      // student / teacher
      { path: 'menu', element: guard(<MenuPage />, CUSTOMER) },
      { path: 'orders', element: guard(<OrdersPage />, CUSTOMER) },
      // cook
      { path: 'kitchen', element: guard(<KitchenPage />, KITCHEN) },
      // cashier
      { path: 'pickup', element: guard(<PickupPage />, PICKUP) },
      { path: 'pos', element: guard(<PosPage />, PICKUP) },
      // canteen_manager
      { path: 'manager', element: guard(<ManagerDashboardPage />, MANAGER) },
      // admin
      { path: 'admin', element: guard(<AdminPage />, ADMIN) },
      { path: '*', element: <PlaceholderPage titleKey="pages.notFound" /> },
    ],
  },
];
