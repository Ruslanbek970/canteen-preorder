#!/bin/sh
# Runs on the server from .github/workflows/deploy.yml (SPEC 14.7), in the deploy directory
# that holds docker-compose.prod.yml, infra/ and .env:
#   sh infra/deploy.sh <image tag>
# Pulls the images of that commit, applies migrations, restarts the stack and checks
# /api/v1/health/ready. If the new version does not get healthy, the previous tag is started
# again. Migrations are not rolled back: they are written to be additive (old code keeps working).
set -eu

TAG="${1:?usage: deploy.sh TAG}"
cd "$(dirname "$0")/.."
DC="docker compose -f docker-compose.prod.yml"
PREVIOUS="$(cat .deployed_tag 2>/dev/null || true)"

ready() {
  $DC exec -T backend python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/ready', timeout=3)" \
    >/dev/null 2>&1
}

echo "deploy: $TAG (previous: ${PREVIOUS:-none})"
export IMAGE_TAG="$TAG"
$DC pull --quiet
$DC up -d db redis
$DC run --rm backend alembic upgrade head
$DC up -d --remove-orphans

for _ in $(seq 1 30); do
  if ready; then
    echo "$TAG" > .deployed_tag
    docker image prune -f >/dev/null
    echo "deploy: $TAG is live"
    exit 0
  fi
  sleep 5
done

echo "deploy: $TAG is not healthy" >&2
$DC logs --tail=50 backend >&2 || true
if [ -n "$PREVIOUS" ]; then
  echo "deploy: rolling back to $PREVIOUS" >&2
  IMAGE_TAG="$PREVIOUS" $DC up -d --remove-orphans
fi
exit 1
