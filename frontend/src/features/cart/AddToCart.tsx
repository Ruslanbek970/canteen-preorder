import { useTranslation } from 'react-i18next';

import type { MenuItem } from '@/api/types';
import { Button } from '@/components/ui';

import { MAX_QUANTITY, useCartStore } from './store';

/** «В корзину» on a dish card; turns into a − n + stepper once the dish is in the cart. */
export function AddToCart({
  item,
  canteenId,
  date,
  disabled,
}: {
  item: MenuItem;
  canteenId: number;
  date: string;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const line = useCartStore((s) =>
    s.canteenId === canteenId && s.date === date
      ? s.lines.find((l) => l.menuItemId === item.id)
      : undefined,
  );
  const add = useCartStore((s) => s.add);
  const setQuantity = useCartStore((s) => s.setQuantity);
  const blocked = disabled || item.unsafe_for_me || item.available_portions === 0;

  if (!line) {
    return (
      <Button
        type="button"
        disabled={blocked}
        onClick={() => add(item, canteenId, date)}
        aria-label={`${t('cart.add')}: ${item.name_ru}`}
      >
        {t('cart.add')}
      </Button>
    );
  }
  const max = Math.min(MAX_QUANTITY, item.available_portions);
  return (
    <div className="flex items-center gap-2" role="group" aria-label={item.name_ru}>
      <Button
        type="button"
        variant="secondary"
        aria-label={t('cart.decrease')}
        onClick={() => setQuantity(item.id, line.quantity - 1)}
      >
        −
      </Button>
      <span className="min-w-6 text-center font-semibold" aria-live="polite">
        {line.quantity}
      </span>
      <Button
        type="button"
        variant="secondary"
        aria-label={t('cart.increase')}
        disabled={line.quantity >= max}
        onClick={() => add(item, canteenId, date)}
      >
        +
      </Button>
    </div>
  );
}
