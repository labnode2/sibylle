#!/usr/bin/env bash
# Production backup: the database (pg_dump in custom format, already compressed) and the
# uploaded images (an archive of the uploads folder), in BACKUP_DIR (backups/ next to deploy/ by
# default), kept BACKUP_KEEP_DAYS days (14). sibylle-backup.timer runs it every night, and
# deploy/update.sh before each update. At night, when BACKUP_AGE_RECIPIENT and BACKUP_REMOTE are
# set (deploy/.env), a copy encrypted with age also goes to the VPS, through rsync.
#   deploy/backup/backup.sh [label]    nightly by default; pre-deploy from update.sh
# Writes the path of the database backup to standard output, the rest to standard error.
set -euo pipefail

main() {
  DEPLOY_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
  # shellcheck source=../lib.sh
  . "$DEPLOY_DIR/lib.sh"

  local label=${1:-nightly}
  [[ $label =~ ^[a-z-]+$ ]] || fail "invalid label: $label"
  local dir keep
  dir=$(setting BACKUP_DIR "$DEPLOY_DIR/../backups")
  keep=$(setting BACKUP_KEEP_DAYS 14)
  umask 077
  mkdir -p "$dir"
  local base
  base="$(cd "$dir" && pwd)/sibylle-$(date +%Y%m%d-%H%M%S)-$label"

  log "Database -> $base.dump"
  compose exec -T db sh -c \
    'pg_dump --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --format=custom' \
    >"$base.dump.part"
  mv "$base.dump.part" "$base.dump"

  log "Uploaded images -> $base.uploads.tar.gz"
  compose run --rm --no-deps -T --entrypoint tar api -C /data -czf - uploads \
    >"$base.uploads.tar.gz.part"
  mv "$base.uploads.tar.gz.part" "$base.uploads.tar.gz"

  find "$dir" -maxdepth 1 -type f -name 'sibylle-*' -mtime "+$keep" -delete
  if [[ $label == nightly ]]; then
    offsite "$base"
  fi
  printf '%s\n' "$base.dump"
}

# Encrypted offsite copy: only the holder of the age private key can read it.
offsite() {
  local base=$1 recipient remote file
  recipient=$(setting BACKUP_AGE_RECIPIENT)
  remote=$(setting BACKUP_REMOTE)
  if [[ -z $recipient || -z $remote ]]; then
    return 0
  fi
  command -v age >/dev/null || fail "age is not installed: no offsite copy"
  for file in "$base.dump" "$base.uploads.tar.gz"; do
    age --encrypt --recipient "$recipient" --output "$file.age" "$file"
  done
  log "Encrypted copy -> $remote"
  rsync --remove-source-files "$base.dump.age" "$base.uploads.tar.gz.age" "$remote"
}

main "$@"
exit
