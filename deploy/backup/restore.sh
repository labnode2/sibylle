#!/usr/bin/env bash
# Restauration d'une sauvegarde de backup.sh : la base, et les images envoyées si leur archive
# est donnée. L'API et le worker s'arrêtent, tout est remplacé, puis ils repartent. Marche aussi
# sur une machine neuve : la base démarre d'abord si besoin.
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
    fail "usage : restore.sh --yes <sauvegarde.dump> [<sauvegarde.uploads.tar.gz>]"
  fi
  if ((!confirmed)); then
    fail "la base de production serait remplacée par $dump${uploads:+, et les images envoyées par $uploads} : relancer avec --yes"
  fi

  compose up -d --wait db
  log "Arrêt de l'API et du worker"
  compose stop api worker
  log "Base <- $dump"
  compose exec -T db sh -c \
    'pg_restore --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --clean --if-exists --no-owner --single-transaction' \
    <"$dump"
  if [[ -n $uploads ]]; then
    log "Images envoyées <- $uploads"
    compose run --rm --no-deps -T --entrypoint sh api \
      -c 'find /data/uploads -mindepth 1 -delete && tar -xzf - -C /data' <"$uploads"
  fi
  log "Relance de l'API et du worker"
  compose up -d --wait api worker
  log "Restauration faite."
}

main "$@"
exit
