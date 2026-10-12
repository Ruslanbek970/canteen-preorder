import type { RouteObject } from 'react-router-dom';

import { AdminPage } from '@/features/admin/AdminPage';
import { LoginPage } from '@/features/auth/LoginPage';
import { KitchenPage } from '@/features/kitchen/KitchenPage';
import { ManagerDashboardPage } from '@/features/manager/ManagerDashboardPage';
import { MenuPage } from '@/features/menu/MenuPage';
import { PublicCanteenPage } from '@/features/menu/PublicCanteenPage';
import { OrdersPage } from '@/features/orders/OrdersPage';
import { PickupPage } from '@/features/pickup/PickupPage';
import { PosPage } from '@/features/pos/PosPage';
import { ProfilePage } from '@/features/profile/ProfilePage';
import { PlaceholderPage } from '@/components/PlaceholderPage';

import { HomePage } from './HomePage';
import { Layout } from './Layout';

// Role guards are added in phase 1 together with authentication.
export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'c/:slug', element: <PublicCanteenPage /> },
      // student / teacher
      { path: 'menu', element: <MenuPage /> },
      { path: 'orders', element: <OrdersPage /> },
      { path: 'profile', element: <ProfilePage /> },
      // cook
      { path: 'kitchen', element: <KitchenPage /> },
      // cashier
      { path: 'pickup', element: <PickupPage /> },
      { path: 'pos', element: <PosPage /> },
      // canteen_manager
      { path: 'manager', element: <ManagerDashboardPage /> },
      // admin
      { path: 'admin', element: <AdminPage /> },
      { path: '*', element: <PlaceholderPage titleKey="pages.notFound" /> },
    ],
  },
];
