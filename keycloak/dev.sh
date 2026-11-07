#!/usr/bin/env bash
# A Keycloak to look at Sibylle's theme and to check it (check-theme.py): the version production
# runs, in dev mode (no theme cache: an edit in keycloak/theme shows on the next reload), with the
# realm of dev-realm.json, on http://localhost:8280 (KEYCLOAK_PORT). Its e-mails go to Mailpit on
# 127.0.0.1:1025: the one of `make db`, or the CI's. It shares the machine's network for that,
# listening on 127.0.0.1 only.
#   keycloak/dev.sh start   start it (a new realm each time) and wait until it answers
#   keycloak/dev.sh stop    stop it
#   keycloak/dev.sh logs    follow its log
set -euo pipefail

# The version of dev-external/keycloak in labnode2/docker: change both together.
IMAGE=quay.io/keycloak/keycloak:26.8.2
NAME=sibylle-keycloak-dev
PORT=${KEYCLOAK_PORT:-8280}
MANAGEMENT_PORT=${KEYCLOAK_MANAGEMENT_PORT:-9280}
DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

start() {
  if docker container inspect "$NAME" >/dev/null 2>&1; then
    echo "$NAME is already running: keycloak/dev.sh stop first." >&2
    exit 1
  fi
  # The local admin (admin, admin) only reaches 127.0.0.1; check-theme.py uses it to send the
  # e-mails an app asks for.
  docker run --detach --rm --name "$NAME" --network host \
    --volume "$DIR/theme:/opt/keycloak/themes/sibylle:ro" \
    --volume "$DIR/dev-realm.json:/opt/keycloak/data/import/sibylle.json:ro" \
    --env KC_BOOTSTRAP_ADMIN_USERNAME=admin --env KC_BOOTSTRAP_ADMIN_PASSWORD=admin \
    "$IMAGE" start-dev --import-realm --health-enabled=true \
    --http-host=127.0.0.1 --http-port="$PORT" --http-management-port="$MANAGEMENT_PORT" >/dev/null
  echo "Starting Keycloak ($IMAGE)..."
  local waited=0
  until curl --silent --fail --output /dev/null "http://127.0.0.1:$MANAGEMENT_PORT/health/ready"; do
    if ((waited >= 180)) || ! docker container inspect "$NAME" >/dev/null 2>&1; then
      echo "Keycloak is not ready after ${waited} s:" >&2
      docker logs --tail 40 "$NAME" >&2 || true
      exit 1
    fi
    sleep 2
    waited=$((waited + 2))
  done
  echo "Keycloak is ready. Sign-in page: http://localhost:$PORT/realms/sibylle/account"
  echo "Accounts: camille@sibylle.test / gazette-camille, dominique@sibylle.test / gazette-dominique" \
    "(asked for a new password), and the demo newsroom's (backend/seed/README.md)." \
    "Admin console: http://localhost:$PORT/admin/ (admin / admin)."
}

case ${1:-} in
  start) start ;;
  stop) docker stop "$NAME" >/dev/null && echo "Keycloak stopped." ;;
  logs) docker logs --follow "$NAME" ;;
  *)
    echo "Usage: $0 start|stop|logs" >&2
    exit 2
    ;;
esac
