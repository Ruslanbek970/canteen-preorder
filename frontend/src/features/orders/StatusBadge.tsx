import { useTranslation } from 'react-i18next';

import type { OrderStatus } from '@/api/types';
import { Badge } from '@/components/ui';

const TONES: Record<OrderStatus, 'gray' | 'green' | 'red' | 'amber' | 'blue'> = {
  pending_payment: 'amber',
  paid: 'blue',
  cooking: 'blue',
  ready: 'green',
  picked_up: 'gray',
  cancelled: 'gray',
  no_show: 'red',
};

export function StatusBadge({ status }: { status: OrderStatus }) {
  const { t } = useTranslation();
  return <Badge tone={TONES[status]}>{t(`orders.status.${status}`)}</Badge>;
}
