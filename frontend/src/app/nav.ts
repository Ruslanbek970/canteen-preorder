import type { Role } from '@/api/types';

export interface NavItem {
  to: string;
  labelKey: string;
}

const CUSTOMER_NAV: NavItem[] = [
  { to: '/menu', labelKey: 'nav.menu' },
  { to: '/cart', labelKey: 'nav.cart' },
  { to: '/orders', labelKey: 'nav.orders' },
  { to: '/profile', labelKey: 'nav.profile' },
];

export const NAV: Record<Role, NavItem[]> = {
  student: CUSTOMER_NAV,
  teacher: CUSTOMER_NAV,
  cook: [
    { to: '/kitchen', labelKey: 'nav.kitchen' },
    { to: '/profile', labelKey: 'nav.profile' },
  ],
  cashier: [
    { to: '/pickup', labelKey: 'nav.pickup' },
    { to: '/pos', labelKey: 'nav.pos' },
    { to: '/profile', labelKey: 'nav.profile' },
  ],
  canteen_manager: [
    { to: '/manager', labelKey: 'nav.dashboard' },
    { to: '/kitchen', labelKey: 'nav.kitchen' },
    { to: '/pickup', labelKey: 'nav.pickup' },
    { to: '/profile', labelKey: 'nav.profile' },
  ],
  admin: [
    { to: '/admin', labelKey: 'nav.admin' },
    { to: '/manager', labelKey: 'nav.dashboard' },
    { to: '/profile', labelKey: 'nav.profile' },
  ],
};
