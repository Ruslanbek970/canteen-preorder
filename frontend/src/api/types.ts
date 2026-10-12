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

export interface MenuItem {
  id: number;
  dish_id: number;
  name_ru: string;
  name_kk: string | null;
  description: string | null;
  category_id: number;
  category_name: string;
  category_sort: number;
  price: string;
  price_now: string;
  discount_percent: number | null;
  promotion_id: number | null;
  available_portions: number;
  portion_grams: number | null;
  calories: number | null;
  protein_g: string | null;
  fat_g: string | null;
  carbs_g: string | null;
  is_halal: boolean;
  is_vegetarian: boolean;
  photo_url: string | null;
  allergens: Allergen[];
  rating: number | null;
  rating_count: number;
  unsafe_for_me: boolean;
  warning_for_me: boolean;
  my_allergens: string[];
}

export interface MenuResponse {
  canteen_id: number;
  date: string;
  available_dates: string[];
  items: MenuItem[];
}

export interface IngredientLine {
  ingredient_id: number;
  name: string;
  unit: string;
  quantity: string;
}

export interface Review {
  rating: number;
  comment: string | null;
  created_at: string;
}

export interface DishDetail {
  id: number;
  name_ru: string;
  name_kk: string | null;
  description: string | null;
  category_id: number;
  category_name: string;
  base_price: string;
  portion_grams: number | null;
  calories: number | null;
  protein_g: string | null;
  fat_g: string | null;
  carbs_g: string | null;
  shelf_life_hours: number;
  is_halal: boolean;
  is_vegetarian: boolean;
  photo_url: string | null;
  is_active: boolean;
  ingredients: IngredientLine[];
  allergens: Allergen[];
  rating: number | null;
  rating_count: number;
  reviews: Review[];
  unsafe_for_me: boolean;
  warning_for_me: boolean;
}

export interface ManagerDish extends Omit<
  DishDetail,
  'reviews' | 'rating' | 'rating_count' | 'unsafe_for_me' | 'warning_for_me'
> {
  category_name: string;
}

export interface Ingredient {
  id: number;
  name: string;
  unit: 'g' | 'ml' | 'pcs';
  allergens: Allergen[];
}

export interface ManagerMenuItem {
  id: number;
  dish_id: number;
  dish_name: string;
  category_name: string;
  price: string;
  planned_portions: number;
  available_portions: number;
  sold_portions: number;
  forecast_portions: number | null;
  forecast_model: string | null;
  cooked_at: string | null;
  allergens: Allergen[];
}

export interface ManagerMenu {
  canteen_id: number;
  date: string;
  items: ManagerMenuItem[];
  synthetic_history: boolean;
}

export interface Slot {
  id: number;
  slot_date: string;
  starts_at: string;
  ends_at: string;
  capacity: number;
  booked_count: number;
  free: number;
  is_closed: boolean;
  discount_percent: number | null;
  promotion_id: number | null;
}

export interface SlotsResponse {
  canteen_id: number;
  date: string;
  slots: Slot[];
  hidden: { by_schedule: number; too_late: number; full: number; closed: number };
  total: number;
  cutoff_minutes: number;
  schedule_applied: boolean;
}

export interface ManagerSlots {
  canteen_id: number;
  date: string;
  slots: Slot[];
}

export type OrderStatus =
  'pending_payment' | 'paid' | 'cooking' | 'ready' | 'picked_up' | 'cancelled' | 'no_show';

export interface OrderItem {
  id: number;
  menu_item_id: number;
  dish_id: number;
  name_ru: string;
  name_kk: string | null;
  quantity: number;
  unit_price: string;
  discount_amount: string;
  line_total: string;
  promotion_id: number | null;
}

export interface Order {
  id: number;
  order_number: string;
  canteen_id: number;
  canteen_name: string;
  service_date: string;
  channel: 'mobile_app' | 'web_qr' | 'cashier';
  status: OrderStatus;
  pickup_slot: { id: number; slot_date: string; starts_at: string; ends_at: string } | null;
  subtotal: string;
  discount_total: string;
  total: string;
  qr_token: string;
  pickup_shelf: number | null;
  allergy_warning_ack: boolean;
  created_at: string;
  paid_at: string | null;
  ready_at: string | null;
  picked_up_at: string | null;
  items: OrderItem[];
  payment_id: number | null;
  payment_url: string | null;
  can_cancel: boolean;
  cancel_until: string | null;
  no_show_warning: boolean;
}

export interface OrderList {
  items: Order[];
  total: number;
}

export interface RepeatResponse {
  canteen_id: number;
  date: string;
  items: {
    menu_item_id: number;
    dish_id: number;
    name_ru: string;
    name_kk: string | null;
    price: string;
    discount_percent: number | null;
    quantity: number;
    available_portions: number;
    warning_for_me: boolean;
  }[];
  skipped: { dish_id: number; name_ru: string; reason: 'not_on_menu' | 'sold_out' | 'allergy' }[];
}
