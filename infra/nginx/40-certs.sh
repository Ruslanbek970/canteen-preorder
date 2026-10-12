#!/bin/sh
# Runs before nginx starts (/docker-entrypoint.d). Let's Encrypt needs nginx on port 80 to issue
# the first certificate, and nginx cannot listen on 443 without one. So until the certificate
# exists nginx serves the app over HTTP (http.conf.template); a background loop switches to
# HTTPS (https.conf.template) as soon as certbot has it and reloads nginx after renewals.
set -eu

LIVE="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
CONF="/etc/nginx/conf.d/default.conf"

render() {
  if [ -f "$LIVE" ]; then mode=https; else mode=http; fi
  envsubst '${DOMAIN}' < "/etc/nginx/canteen/${mode}.conf.template" > "$CONF.new"
  if ! cmp -s "$CONF.new" "$CONF"; then
    mv "$CONF.new" "$CONF"
    echo "40-certs.sh: nginx in ${mode} mode"
    return 0
  fi
  rm -f "$CONF.new"
  return 1
}

render || true
(
  while :; do
    if [ -f "$LIVE" ]; then sleep 21600; else sleep 300; fi
    render || true
    nginx -s reload 2>/dev/null || true
  done
) &
