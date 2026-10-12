import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiDelete, apiGet, apiPost } from '@/api/client';
import type { Me, TelegramLinkCode } from '@/api/types';
import { Alert, Button, Card } from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';
import { ME_KEY } from '@/features/auth/useMe';
import {
  currentSubscription,
  disablePush,
  enablePush,
  fetchPushKey,
  pushSupported,
} from '@/features/notifications/push';

/** Profile card: link a Telegram chat and switch browser notifications on or off. */
export function NotificationSettings({ me }: { me: Me }) {
  const { t } = useTranslation();
  return (
    <Card className="space-y-4">
      <h2 className="font-medium">{t('profile.notifications.title')}</h2>
      <p className="text-sm text-slate-500">{t('profile.notifications.hint')}</p>
      <TelegramLink linked={me.telegram_linked} />
      <PushToggle />
    </Card>
  );
}

function TelegramLink({ linked }: { linked: boolean }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const [code, setCode] = useState<TelegramLinkCode | null>(null);
  // While a code is shown, watch the profile so the card flips as soon as the bot links it.
  useQuery({
    queryKey: ME_KEY,
    queryFn: () => apiGet<Me>('/me'),
    enabled: code !== null && !linked,
    refetchInterval: 4000,
  });
  const getCode = useMutation({
    mutationFn: () => apiPost<TelegramLinkCode>('/me/telegram/link-code'),
    onSuccess: setCode,
  });
  const unlink = useMutation({
    mutationFn: () => apiDelete<void>('/me/telegram'),
    onSuccess: () => {
      setCode(null);
      client.setQueryData<Me>(ME_KEY, (old) => (old ? { ...old, telegram_linked: false } : old));
    },
  });
  const error = getCode.error ?? unlink.error;
  return (
    <div className="space-y-2 border-t border-slate-200 pt-3 dark:border-slate-800">
      <p className="font-medium">Telegram</p>
      {error && <Alert>{errorMessage(error)}</Alert>}
      {linked ? (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm text-brand-700 dark:text-brand-400">
            {t('profile.notifications.telegramLinked')}
          </span>
          <Button variant="secondary" disabled={unlink.isPending} onClick={() => unlink.mutate()}>
            {t('profile.notifications.unlink')}
          </Button>
        </div>
      ) : code ? (
        <div className="space-y-2 text-sm">
          <p>{t('profile.notifications.sendCode')}</p>
          <p className="select-all rounded-lg bg-slate-100 p-2 text-center font-mono text-2xl tracking-widest dark:bg-slate-800">
            /start {code.code}
          </p>
          {code.deep_link && (
            <a
              href={code.deep_link}
              target="_blank"
              rel="noreferrer"
              className="block text-center font-medium text-brand-700 underline dark:text-brand-400"
            >
              {t('profile.notifications.openBot', { bot: `@${code.bot_username ?? ''}` })}
            </a>
          )}
          <p className="text-xs text-slate-500">
            {t('profile.notifications.codeExpires', { minutes: Math.round(code.expires_in / 60) })}
          </p>
        </div>
      ) : (
        <Button variant="secondary" disabled={getCode.isPending} onClick={() => getCode.mutate()}>
          {t('profile.notifications.linkTelegram')}
        </Button>
      )}
    </div>
  );
}

function PushToggle() {
  const { t } = useTranslation();
  const errorMessage = useErrorMessage();
  const supported = pushSupported();
  const state = useQuery({
    queryKey: ['push', 'state'],
    enabled: supported,
    queryFn: async () => {
      const [key, subscription] = await Promise.all([fetchPushKey(), currentSubscription()]);
      return { key, enabled: subscription !== null };
    },
  });
  const [denied, setDenied] = useState(false);
  const toggle = useMutation({
    mutationFn: async (on: boolean) => {
      if (!on) return disablePush();
      const result = await enablePush(state.data?.key ?? '');
      if (result === 'denied') setDenied(true);
    },
    onSettled: () => void state.refetch(),
  });

  let body;
  if (!supported)
    body = <p className="text-sm text-slate-500">{t('profile.notifications.pushUnsupported')}</p>;
  else if (state.isPending) body = null;
  else if (state.isError) body = <Alert>{errorMessage(state.error)}</Alert>;
  else if (state.data.key === null)
    body = <p className="text-sm text-slate-500">{t('profile.notifications.pushOff')}</p>;
  else
    body = (
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          className="h-5 w-5"
          checked={state.data.enabled}
          disabled={toggle.isPending}
          onChange={(e) => toggle.mutate(e.target.checked)}
        />
        {t('profile.notifications.pushToggle')}
      </label>
    );
  return (
    <div className="space-y-2 border-t border-slate-200 pt-3 dark:border-slate-800">
      <p className="font-medium">{t('profile.notifications.push')}</p>
      {body}
      {denied && <Alert tone="warning">{t('profile.notifications.pushDenied')}</Alert>}
      {toggle.isError && <Alert>{errorMessage(toggle.error)}</Alert>}
    </div>
  );
}
