#!/usr/bin/env bash
# Restores a backup made by backup.sh: the database, and the uploaded images when their archive
# is given. The API and the worker stop, everything is replaced, then they start again. Also
# works on a fresh machine: the database starts first if needed.
#   deploy/backup/restore.sh --yes backups/sibylle-…-nightly.dump [backups/sibylle-…-nightly.uploads.tar.gz]
set -euo pipefail

main() {
  DEPLOY_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
  # shellcheck source=../lib.sh
  . "$DEPLOY_DIR/lib.sh"

  local confirmed=0
  if [[ ${1-} == --yes ]]; then
    confirmed=1
    shift
  fi
  local dump=${1-} uploads=${2-}
  if [[ ! -f $dump || (-n $uploads && ! -f $uploads) ]]; then
    fail "usage: restore.sh --yes <backup.dump> [<backup.uploads.tar.gz>]"
  fi
  if ((!confirmed)); then
    fail "the production database would be replaced by $dump${uploads:+, and the uploaded images by $uploads}: run again with --yes"
  fi

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
  log "Restore done."
}

main "$@"
exit
