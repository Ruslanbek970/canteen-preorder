#!/bin/sh
# Restore a dump made by backup.sh (SPEC 14.9).
#   restore.sh FILE              - into the test database canteen_restore_test (safe check)
#   restore.sh FILE canteen      - over the working database (stop backend and worker first)
# Prints row counts of the main tables, to compare with the source database.
set -eu

FILE="${1:?usage: restore.sh FILE [DATABASE]}"
TARGET="${2:-canteen_restore_test}"

if [ "$TARGET" != "${PGDATABASE:-canteen}" ]; then
  dropdb --if-exists "$TARGET"
  createdb "$TARGET"
fi
pg_restore --clean --if-exists --no-owner --exit-on-error --dbname="$TARGET" "$FILE"

echo "restored $FILE into $TARGET:"
psql --dbname="$TARGET" --no-psqlrc --tuples-only --command="
  SELECT 'users', count(*) FROM users UNION ALL
  SELECT 'orders', count(*) FROM orders UNION ALL
  SELECT 'order_items', count(*) FROM order_items UNION ALL
  SELECT 'menu_items', count(*) FROM menu_items UNION ALL
  SELECT 'payments', count(*) FROM payments UNION ALL
  SELECT 'alembic_version', count(*) FROM alembic_version"
