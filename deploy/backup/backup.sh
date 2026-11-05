#!/usr/bin/env bash
# Sauvegarde de la production : la base (pg_dump au format personnalisé, déjà compressé) et les
# images envoyées (archive du volume uploads), dans BACKUP_DIR (backups/ à côté de deploy/ par
# défaut), gardées BACKUP_KEEP_DAYS jours (14). sibylle-backup.timer la lance chaque nuit, et
# deploy/update.sh avant chaque mise à jour. La nuit, si BACKUP_AGE_RECIPIENT et BACKUP_REMOTE
# sont posés (deploy/.env), une copie chiffrée avec age part aussi sur le VPS, par rsync.
#   deploy/backup/backup.sh [étiquette]    nightly par défaut ; pre-deploy depuis update.sh
# Écrit le chemin de la sauvegarde de la base sur la sortie standard, le reste sur l'erreur.
set -euo pipefail

main() {
  DEPLOY_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
  # shellcheck source=../lib.sh
  . "$DEPLOY_DIR/lib.sh"

  local label=${1:-nightly}
  [[ $label =~ ^[a-z-]+$ ]] || fail "étiquette invalide : $label"
  local dir keep
  dir=$(setting BACKUP_DIR "$DEPLOY_DIR/../backups")
  keep=$(setting BACKUP_KEEP_DAYS 14)
  umask 077
  mkdir -p "$dir"
  local base
  base="$(cd "$dir" && pwd)/sibylle-$(date +%Y%m%d-%H%M%S)-$label"

  log "Base -> $base.dump"
  compose exec -T db sh -c \
    'pg_dump --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --format=custom' \
    >"$base.dump.part"
  mv "$base.dump.part" "$base.dump"

  log "Images envoyées -> $base.uploads.tar.gz"
  compose run --rm --no-deps -T --entrypoint tar api -C /data -czf - uploads \
    >"$base.uploads.tar.gz.part"
  mv "$base.uploads.tar.gz.part" "$base.uploads.tar.gz"

  find "$dir" -maxdepth 1 -type f -name 'sibylle-*' -mtime "+$keep" -delete
  if [[ $label == nightly ]]; then
    offsite "$base"
  fi
  printf '%s\n' "$base.dump"
}

# Copie chiffrée hors site : seul le détenteur de la clé privée age peut la lire.
offsite() {
  local base=$1 recipient remote file
  recipient=$(setting BACKUP_AGE_RECIPIENT)
  remote=$(setting BACKUP_REMOTE)
  if [[ -z $recipient || -z $remote ]]; then
    return 0
  fi
  command -v age >/dev/null || fail "age n'est pas installé : pas de copie hors site"
  for file in "$base.dump" "$base.uploads.tar.gz"; do
    age --encrypt --recipient "$recipient" --output "$file.age" "$file"
  done
  log "Copie chiffrée -> $remote"
  rsync --remove-source-files "$base.dump.age" "$base.uploads.tar.gz.age" "$remote"
}

main "$@"
exit
