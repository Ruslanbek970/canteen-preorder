#!/bin/sh
# Daily database backup (SPEC 14.9). Runs in the `backup` service of docker-compose.prod.yml:
# every day at BACKUP_HOUR (local time, TZ) a pg_dump in custom format goes to BACKUP_DIR,
# dumps older than BACKUP_KEEP_DAYS are deleted.
#   backup.sh        - run forever, one dump a day
#   backup.sh once   - one dump now (`make backup`)
# Connection: the standard PGHOST, PGUSER, PGPASSWORD, PGDATABASE variables.
set -eu

DIR="${BACKUP_DIR:-/backups}"
KEEP="${BACKUP_KEEP_DAYS:-14}"
HOUR="${BACKUP_HOUR:-03}"

dump() {
  mkdir -p "$DIR"
  file="$DIR/canteen-$(date +%Y%m%d-%H%M%S).dump"
  pg_dump --format=custom --file="$file.part"
  mv "$file.part" "$file"
  find "$DIR" -name 'canteen-*.dump' -mtime +"$KEEP" -delete
  echo "backup: $file $(du -h "$file" | cut -f1)"
}

if [ "${1:-}" = "once" ]; then
  dump
  exit 0
fi

echo "backup: daily at ${HOUR}:00, keeping ${KEEP} days in ${DIR}"
while true; do
  now=$(date +%s)
  next=$(date -d "$(date +%Y-%m-%d) ${HOUR}:00:00" +%s)
  if [ "$next" -le "$now" ]; then next=$((next + 86400)); fi
  sleep $((next - now))
  dump || echo "backup: FAILED" >&2
done
