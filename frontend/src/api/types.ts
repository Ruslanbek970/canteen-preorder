// API response types (backend app/schemas).

export type Role = 'student' | 'teacher' | 'cook' | 'cashier' | 'canteen_manager' | 'admin';
export type Language = 'ru' | 'kk' | 'en';
export type Severity = 'mild' | 'moderate' | 'severe';

export interface HealthResponse {
  status: 'ok';
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface Me {
  id: number;
  full_name: string;
  email: string;
  phone: string | null;
  role: Role;
  canteen_id: number | null;
  canteen_name: string | null;
  group_id: number | null;
  group_code: string | null;
  preferred_language: Language;
  email_verified: boolean;
  health_data_consent_at: string | null;
  loyalty_points: number;
  telegram_linked: boolean;
  marketing_opt_out: boolean;
  no_show_count_30d: number;
}

export interface Canteen {
  id: number;
  name: string;
  building_id: number;
  opens_at: string;
  closes_at: string;
  slug: string | null;
  is_active: boolean;
  order_cutoff_minutes: number;
}

export interface Group {
  id: number;
  code: string;
  faculty: string | null;
  study_year: number | null;
}

export interface Allergen {
  id: number;
  code: string;
  name_ru: string;
  name_kk: string | null;
}

export interface Category {
  id: number;
  name: string;
  sort_order: number;
}

export interface UserAllergen {
  allergen_id: number;
  code: string;
  name_ru: string;
  name_kk: string | null;
  severity: Severity;
}

export interface MyAllergens {
  health_data_consent_at: string | null;
  allergens: UserAllergen[];
}
