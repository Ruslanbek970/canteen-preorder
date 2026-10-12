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
import { KitchenWastePage } from '@/features/kitchen/KitchenWastePage';
import { LabelsPage } from '@/features/kitchen/LabelsPage';
import { CartPage } from '@/features/cart/CartPage';
import { DishesPage } from '@/features/manager/DishesPage';
import { IngredientsPage } from '@/features/manager/IngredientsPage';
import { ManagerDashboardPage } from '@/features/manager/ManagerDashboardPage';
import { ManagerMenuPage } from '@/features/manager/ManagerMenuPage';
import { ManagerSlotsPage } from '@/features/manager/ManagerSlotsPage';
import { DishPage } from '@/features/menu/DishPage';
import { MenuPage } from '@/features/menu/MenuPage';
import { PublicCanteenPage } from '@/features/menu/PublicCanteenPage';
import { OrderPage } from '@/features/orders/OrderPage';
import { OrdersPage } from '@/features/orders/OrdersPage';
import { MockPaymentPage } from '@/features/payments/MockPaymentPage';
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
      { path: 'dishes/:id', element: <DishPage /> },
      { path: 'onboarding', element: guard(<OnboardingPage />, CUSTOMER) },
      { path: 'profile', element: guard(<ProfilePage />) },
      // student / teacher
      { path: 'menu', element: guard(<MenuPage />, CUSTOMER) },
      { path: 'cart', element: guard(<CartPage />, CUSTOMER) },
      { path: 'orders', element: guard(<OrdersPage />, CUSTOMER) },
      { path: 'orders/:id', element: guard(<OrderPage />, CUSTOMER) },
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
      { path: 'manager/menu', element: guard(<ManagerMenuPage />, MANAGER) },
      { path: 'manager/slots', element: guard(<ManagerSlotsPage />, MANAGER) },
      { path: 'manager/dishes', element: guard(<DishesPage />, MANAGER) },
      { path: 'manager/ingredients', element: guard(<IngredientsPage />, MANAGER) },
      // admin
      { path: 'admin', element: guard(<AdminPage />, ADMIN) },
      { path: '*', element: <PlaceholderPage titleKey="pages.notFound" /> },
    ],
  },
];
