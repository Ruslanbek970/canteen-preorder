import { lazy, Suspense, type ReactElement } from 'react';
import type { RouteObject } from 'react-router-dom';

import type { Role } from '@/api/types';

import { PlaceholderPage } from '@/components/PlaceholderPage';
import { LoadingState } from '@/components/ui';
import { LoginPage } from '@/features/auth/LoginPage';
import { OnboardingPage } from '@/features/auth/OnboardingPage';
import { RegisterPage } from '@/features/auth/RegisterPage';
import { VerifyEmailPage } from '@/features/auth/VerifyEmailPage';
import { CartPage } from '@/features/cart/CartPage';
import { DishPage } from '@/features/menu/DishPage';
import { MenuPage } from '@/features/menu/MenuPage';
import { NotificationsPage } from '@/features/notifications/NotificationsPage';
import { PublicCanteenPage } from '@/features/menu/PublicCanteenPage';
import { OrderPage } from '@/features/orders/OrderPage';
import { OrdersPage } from '@/features/orders/OrdersPage';
import { MockPaymentPage } from '@/features/payments/MockPaymentPage';
import { ProfilePage } from '@/features/profile/ProfilePage';

import { RedirectIfSignedIn, RequireRole } from './guards';
import { HomePage } from './HomePage';
import { Layout } from './Layout';
import { ADMIN, CUSTOMER, KITCHEN, MANAGER, PICKUP } from './roles';

// Staff screens (charts, the QR scanner) are loaded only by the people who open them, so the
// student's phone downloads just the customer part of the app.
const AdminBuildingsPage = lazy(() =>
  import('@/features/admin/AdminBuildingsPage').then((m) => ({ default: m.AdminBuildingsPage })),
);
const AdminCanteensPage = lazy(() =>
  import('@/features/admin/AdminCanteensPage').then((m) => ({ default: m.AdminCanteensPage })),
);
const AdminGroupsPage = lazy(() =>
  import('@/features/admin/AdminGroupsPage').then((m) => ({ default: m.AdminGroupsPage })),
);
const AdminSchedulePage = lazy(() =>
  import('@/features/admin/AdminSchedulePage').then((m) => ({ default: m.AdminSchedulePage })),
);
const AdminUsersPage = lazy(() =>
  import('@/features/admin/AdminUsersPage').then((m) => ({ default: m.AdminUsersPage })),
);
const KitchenPage = lazy(() =>
  import('@/features/kitchen/KitchenPage').then((m) => ({ default: m.KitchenPage })),
);
const KitchenWastePage = lazy(() =>
  import('@/features/kitchen/KitchenWastePage').then((m) => ({ default: m.KitchenWastePage })),
);
const LabelsPage = lazy(() =>
  import('@/features/kitchen/LabelsPage').then((m) => ({ default: m.LabelsPage })),
);
const DishesPage = lazy(() =>
  import('@/features/manager/DishesPage').then((m) => ({ default: m.DishesPage })),
);
const IngredientsPage = lazy(() =>
  import('@/features/manager/IngredientsPage').then((m) => ({ default: m.IngredientsPage })),
);
const ManagerDashboardPage = lazy(() =>
  import('@/features/manager/ManagerDashboardPage').then((m) => ({
    default: m.ManagerDashboardPage,
  })),
);
const ManagerMenuPage = lazy(() =>
  import('@/features/manager/ManagerMenuPage').then((m) => ({ default: m.ManagerMenuPage })),
);
const PromotionsPage = lazy(() =>
  import('@/features/manager/PromotionsPage').then((m) => ({ default: m.PromotionsPage })),
);
const ManagerSlotsPage = lazy(() =>
  import('@/features/manager/ManagerSlotsPage').then((m) => ({ default: m.ManagerSlotsPage })),
);
const PickupPage = lazy(() =>
  import('@/features/pickup/PickupPage').then((m) => ({ default: m.PickupPage })),
);
const PosPage = lazy(() => import('@/features/pos/PosPage').then((m) => ({ default: m.PosPage })));
const ReportsPage = lazy(() =>
  import('@/features/manager/ReportsPage').then((m) => ({ default: m.ReportsPage })),
);

const guard = (element: ReactElement, roles?: Role[]) => (
  <RequireRole roles={roles}>
    <Suspense fallback={<LoadingState />}>{element}</Suspense>
  </RequireRole>
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
      { path: 'dishes/:id', element: <DishPage /> },
      { path: 'onboarding', element: guard(<OnboardingPage />, CUSTOMER) },
      { path: 'profile', element: guard(<ProfilePage />) },
      // student / teacher
      { path: 'menu', element: guard(<MenuPage />, CUSTOMER) },
      { path: 'cart', element: guard(<CartPage />, CUSTOMER) },
      { path: 'orders', element: guard(<OrdersPage />, CUSTOMER) },
      { path: 'orders/:id', element: guard(<OrderPage />, CUSTOMER) },
      { path: 'notifications', element: guard(<NotificationsPage />, CUSTOMER) },
      { path: 'pay/mock/:paymentId', element: guard(<MockPaymentPage />, CUSTOMER) },
      // cook
      { path: 'kitchen', element: guard(<KitchenPage />, KITCHEN) },
      { path: 'kitchen/waste', element: guard(<KitchenWastePage />, KITCHEN) },
      { path: 'kitchen/labels', element: guard(<LabelsPage />, KITCHEN) },
      // cashier
      { path: 'pickup', element: guard(<PickupPage />, PICKUP) },
      { path: 'pos', element: guard(<PosPage />, PICKUP) },
      // canteen_manager
      { path: 'manager', element: guard(<ManagerDashboardPage />, MANAGER) },
      {
        path: 'manager/reports',
        element: guard(<ReportsPage />, MANAGER),
      },
      { path: 'manager/promotions', element: guard(<PromotionsPage />, MANAGER) },
      { path: 'manager/menu', element: guard(<ManagerMenuPage />, MANAGER) },
      { path: 'manager/slots', element: guard(<ManagerSlotsPage />, MANAGER) },
      { path: 'manager/dishes', element: guard(<DishesPage />, MANAGER) },
      { path: 'manager/ingredients', element: guard(<IngredientsPage />, MANAGER) },
      // admin
      { path: 'admin', element: guard(<AdminUsersPage />, ADMIN) },
      { path: 'admin/canteens', element: guard(<AdminCanteensPage />, ADMIN) },
      { path: 'admin/buildings', element: guard(<AdminBuildingsPage />, ADMIN) },
      { path: 'admin/groups', element: guard(<AdminGroupsPage />, ADMIN) },
      { path: 'admin/schedule', element: guard(<AdminSchedulePage />, ADMIN) },
      { path: '*', element: <PlaceholderPage titleKey="pages.notFound" /> },
    ],
  },
];
