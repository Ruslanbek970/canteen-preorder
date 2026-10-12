import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiPost } from '@/api/client';
import type { OrderItem } from '@/api/types';
import { Alert, Button } from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';
import { dishName } from '@/lib/names';

import { ORDERS_KEY } from './api';

/** Rate one dish of a picked-up order (SPEC 7.12): 1–5 stars and an optional comment. */
export function ReviewForm({ item }: { item: OrderItem }) {
  const { t, i18n } = useTranslation();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState('');
  const send = useMutation({
    mutationFn: () =>
      apiPost(`/order-items/${item.id}/review`, { rating, comment: comment.trim() || null }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ORDERS_KEY });
      void client.invalidateQueries({ queryKey: ['dish', item.dish_id] });
    },
  });
  const name = dishName(item, i18n.resolvedLanguage);

  if (item.my_rating !== null) {
    return (
      <p className="text-sm">
        {name}:{' '}
        <span className="text-amber-500" aria-label={t('reviews.stars', { count: item.my_rating })}>
          {'★'.repeat(item.my_rating)}
          <span className="text-slate-300">{'★'.repeat(5 - item.my_rating)}</span>
        </span>{' '}
        <span className="text-slate-500">{t('reviews.thanks')}</span>
      </p>
    );
  }
  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (rating) send.mutate();
      }}
    >
      <fieldset>
        <legend className="mb-1 text-sm font-medium">{name}</legend>
        <div className="flex gap-1">
          {[1, 2, 3, 4, 5].map((stars) => (
            <button
              key={stars}
              type="button"
              aria-pressed={rating === stars}
              aria-label={t('reviews.stars', { count: stars })}
              onClick={() => setRating(stars)}
              className={`min-h-[44px] min-w-[44px] text-3xl ${
                stars <= rating ? 'text-amber-500' : 'text-slate-300'
              }`}
            >
              ★
            </button>
          ))}
        </div>
      </fieldset>
      {rating > 0 && (
        <>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={1000}
            rows={2}
            placeholder={t('reviews.commentPlaceholder')}
            aria-label={t('reviews.comment')}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 dark:border-slate-700 dark:bg-slate-900"
          />
          <Button type="submit" disabled={send.isPending}>
            {t('reviews.send')}
          </Button>
        </>
      )}
      {send.isError && <Alert tone="error">{errorMessage(send.error)}</Alert>}
    </form>
  );
}
