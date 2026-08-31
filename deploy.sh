#!/usr/bin/env bash
# Deploy mocker on the VPS. PULLS images — never builds. Run from /opt/mocker.
#
#   ./deploy.sh                       # deploy :latest
#   ./deploy.sh sha-abc1234           # deploy (or roll back to) a specific build
set -euo pipefail

cd "$(dirname "$0")"
COMPOSE="docker compose -f compose.prod.yml"
OWNER="aravindshajan6"
TAG="${1:-latest}"

if [[ ! -f .env ]]; then
  echo "no .env beside compose.prod.yml — run deploy/make-env.sh first" >&2
  echo "(compose reads \${VAR} from a .env in THIS directory; env_file: does not satisfy them)" >&2
  exit 1
fi

export FRONTEND_IMAGE="ghcr.io/${OWNER}/mocker-frontend:${TAG}"
export BACKEND_IMAGE="ghcr.io/${OWNER}/mocker-backend:${TAG}"
echo "==> deploying ${TAG}"
echo "    frontend: ${FRONTEND_IMAGE}"
echo "    backend:  ${BACKEND_IMAGE}"

echo "==> pulling"
$COMPOSE pull

echo "==> starting"
$COMPOSE up -d --remove-orphans

echo "==> waiting for health"
deadline=$(( SECONDS + 180 ))
while (( SECONDS < deadline )); do
  # Ask the daemon, not the app: this is the same signal depends_on and Traefik act on.
  unhealthy=$(docker ps --filter name=mocker- --format '{{.Names}} {{.Status}}' \
              | grep -vc 'healthy' || true)
  if [[ "$unhealthy" == "0" ]]; then
    echo "    all containers healthy"
    break
  fi
  sleep 5
done
if (( SECONDS >= deadline )); then
  echo "!! not healthy within 180s — showing recent logs" >&2
  $COMPOSE ps
  $COMPOSE logs --tail 40 mocker-backend mocker-frontend
  exit 1
fi

echo "==> pruning dangling images only"
# NEVER `docker system prune -a` here: it would delete images belonging to valodex.
docker image prune -f >/dev/null

echo
$COMPOSE ps
echo
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}' \
  | grep -E 'NAME|mocker-'
echo
free -h | head -2
echo
echo "==> external check"
curl -sS -o /dev/null -w '    https://mocker.sapper.top/api/health -> %{http_code}\n' \
  https://mocker.sapper.top/api/health || echo "    (not answering yet; certificate issuance takes 10-30s on first request)"
