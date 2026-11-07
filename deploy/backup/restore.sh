#!/usr/bin/env bash
# Restores a backup made by backup.sh: Sibylle's database, the uploaded images when their archive
# is given, and Keycloak's database (the accounts) with --keycloak. For Sibylle's, the API and the
# worker stop, everything is replaced, then they start again; for Keycloak's, Keycloak stops
# meanwhile, then takes about a minute to start again. Also works on a fresh machine: Sibylle's
# database starts first if needed (Keycloak's stack must be running: labnode2/docker).
#   deploy/backup/restore.sh --yes backups/sibylle-…-nightly.dump [backups/sibylle-…-nightly.uploads.tar.gz]
#   deploy/backup/restore.sh --yes --keycloak backups/sibylle-…-nightly.keycloak.dump [<the above>]
set -euo pipefail

main() {
  DEPLOY_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
  # shellcheck source=../lib.sh
  . "$DEPLOY_DIR/lib.sh"

  local confirmed=0 keycloak=
  while (($#)); do
    case $1 in
      --yes) confirmed=1 ;;
      --keycloak)
        keycloak=${2-}
        shift
        ;;
      *) break ;;
    esac
    shift
  done
  local dump=${1-} uploads=${2-}
  if [[ (-z $dump && -z $keycloak) || (-n $dump && ! -f $dump) ||
    (-n $uploads && ! -f $uploads) || (-n $keycloak && ! -f $keycloak) ]]; then
    fail "usage: restore.sh --yes [--keycloak <backup.keycloak.dump>] [<backup.dump> [<backup.uploads.tar.gz>]]"
  fi
  if ((!confirmed)); then
    local what=()
    [[ -z $keycloak ]] || what+=("Keycloak's database by $keycloak")
    [[ -z $dump ]] || what+=("the production database by $dump")
    [[ -z $uploads ]] || what+=("the uploaded images by $uploads")
    fail "$(IFS=,; echo "${what[*]}" | sed 's/,/, /g') would be replaced: run again with --yes"
  fi

  [[ -z $keycloak ]] || restore_keycloak "$keycloak"
  [[ -z $dump ]] || restore_sibylle "$dump" "$uploads"
  log "Restore done."
}

# restore_keycloak FILE: Keycloak's database, Keycloak stopped (labnode2/docker's containers).
restore_keycloak() {
  local file=$1 keycloak keycloak_db
  keycloak=$(setting KEYCLOAK_CONTAINER keycloak)
  keycloak_db=$(setting KEYCLOAK_DB_CONTAINER keycloak-db)
  [[ $(docker container inspect --format '{{.State.Running}}' "$keycloak_db" 2>/dev/null) == true ]] ||
    fail "$keycloak_db is not running: start Keycloak's stack first (labnode2/docker)"
  log "Stopping Keycloak"
  docker stop "$keycloak" >/dev/null
  log "Keycloak's database <- $file"
  docker exec -i "$keycloak_db" pg_restore --username=keycloak --dbname=keycloak \
    --clean --if-exists --no-owner --single-transaction <"$file"
  log "Starting Keycloak again: it answers about a minute later"
  docker start "$keycloak" >/dev/null
}

# restore_sibylle DUMP [UPLOADS]: Sibylle's database, and its uploaded images.
restore_sibylle() {
  local dump=$1 uploads=${2-}
  compose up -d --wait db
  log "Stopping the API and the worker"
  compose stop api worker
  log "Database <- $dump"
  compose exec -T db sh -c \
    'pg_restore --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --clean --if-exists --no-owner --single-transaction' \
    <"$dump"
  if [[ -n $uploads ]]; then
    log "Uploaded images <- $uploads"
    compose run --rm --no-deps -T --entrypoint sh api \
      -c 'find /data/uploads -mindepth 1 -delete && tar -xzf - -C /data' <"$uploads"
  fi
  log "Starting the API and the worker again"
  compose up -d --wait api worker
}

main "$@"
exit
