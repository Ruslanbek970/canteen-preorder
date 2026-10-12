import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { apiGet, apiPost } from '@/api/client';
import type { PaymentInfo } from '@/api/types';
import { Alert, Button, Card, ErrorState, LoadingState } from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';
import { ORDERS_KEY } from '@/features/orders/api';
import { formatPrice } from '@/lib/format';

/** The mock provider's "payment page" (SPEC 7.7): «Оплатить» or «Отказ». No real money. */
export function MockPaymentPage() {
  const { t } = useTranslation();
  const id = Number(useParams().paymentId);
  const navigate = useNavigate();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const payment = useQuery({
    queryKey: ['payment', id],
    queryFn: () => apiGet<PaymentInfo>(`/payments/${id}`),
  });
  const answer = useMutation({
    mutationFn: (ok: boolean) =>
      apiPost<PaymentInfo>(`/payments/mock/${id}/${ok ? 'confirm' : 'fail'}`),
    onSuccess: (result) => {
      void client.invalidateQueries({ queryKey: ORDERS_KEY });
      navigate(`/orders/${result.order_id}`, { replace: true });
    },
  });

  if (payment.isPending) return <LoadingState />;
  if (payment.isError)
    return (
      <section className="p-4">
        <ErrorState error={payment.error} onRetry={() => void payment.refetch()} />
      </section>
    );
  const p = payment.data;

  return (
    <section className="mx-auto max-w-sm p-4">
      <Card>
        <p className="text-center text-sm uppercase tracking-wide text-slate-500">
          {t('payment.mockTitle')}
        </p>
        <p className="mt-2 text-center text-sm">
          {p.canteen_name} · {t('orders.number')} {p.order_number}
        </p>
        <p className="my-4 text-center text-4xl font-bold">{formatPrice(p.amount)}</p>
        {p.status === 'pending' ? (
          <div className="grid gap-2">
            <Button disabled={answer.isPending} onClick={() => answer.mutate(true)}>
              {t('payment.pay')}
            </Button>
            <Button
              variant="secondary"
              disabled={answer.isPending}
              onClick={() => answer.mutate(false)}
            >
              {t('payment.decline')}
            </Button>
          </div>
        ) : (
          <Alert tone="info">{t(`payment.status.${p.status}`)}</Alert>
        )}
        {answer.isError && (
          <div className="mt-3">
            <Alert tone="error">{errorMessage(answer.error)}</Alert>
          </div>
        )}
        <p className="mt-4 text-center text-xs text-slate-500">{t('payment.mockNote')}</p>
      </Card>
      <p className="mt-4 text-center">
        <Link to={`/orders/${p.order_id}`} className="text-sm text-brand-700 dark:text-brand-400">
          {t('payment.backToOrder')}
        </Link>
      </p>
    </section>
  );
}
