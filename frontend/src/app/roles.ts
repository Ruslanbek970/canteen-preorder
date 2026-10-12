import type { Role } from '@/api/types';

export const CUSTOMER: Role[] = ['student', 'teacher'];
export const KITCHEN: Role[] = ['cook', 'canteen_manager'];
export const PICKUP: Role[] = ['cashier', 'canteen_manager'];
export const MANAGER: Role[] = ['canteen_manager', 'admin'];
export const ADMIN: Role[] = ['admin'];
