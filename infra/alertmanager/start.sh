#!/bin/sh
# Alertmanager does not read environment variables in its config: fill them in here.
set -eu
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${ALERT_TELEGRAM_CHAT_ID:-}" ]; then
  sed -e "s|TELEGRAM_BOT_TOKEN|${TELEGRAM_BOT_TOKEN}|" \
      -e "s|ALERT_TELEGRAM_CHAT_ID|${ALERT_TELEGRAM_CHAT_ID}|" \
      /etc/alertmanager/alertmanager.telegram.yml > /tmp/alertmanager.yml
else
  cp /etc/alertmanager/alertmanager.none.yml /tmp/alertmanager.yml
fi
exec /bin/alertmanager --config.file=/tmp/alertmanager.yml --storage.path=/alertmanager
