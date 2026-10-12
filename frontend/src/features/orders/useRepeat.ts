import { useNavigate } from 'react-router-dom';

import type { Order } from '@/api/types';
import { useCartStore } from '@/features/cart/store';

import { useRepeatOrder } from './api';

/** «Повторить»: fills the cart with what is still available and opens it. */
export function useRepeat() {
  const repeat = useRepeatOrder();
  const replace = useCartStore((s) => s.replace);
  const navigate = useNavigate();
  const run = (order: Order) =>
    repeat.mutate(order.id, {
      onSuccess: (cart) => {
        replace(
          cart.canteen_id,
          cart.date,
          cart.items.map((line) => ({
            menuItemId: line.menu_item_id,
            dishId: line.dish_id,
            nameRu: line.name_ru,
            nameKk: line.name_kk,
            price: line.price,
            discountPercent: line.discount_percent,
            quantity: line.quantity,
            available: line.available_portions,
            warning: line.warning_for_me,
          })),
        );
        navigate('/cart', { state: { skipped: cart.skipped } });
      },
    });
  return { run, isPending: repeat.isPending, error: repeat.error };
}
