// API response types. Extended in later phases as endpoints appear.

export type Role = 'student' | 'teacher' | 'cook' | 'cashier' | 'canteen_manager' | 'admin';

export interface HealthResponse {
  status: 'ok';
}
