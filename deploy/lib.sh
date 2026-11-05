# Outils communs aux scripts de production (update.sh, backup/backup.sh, backup/restore.sh), qui
# posent DEPLOY_DIR (le dossier deploy/ de /opt/sibylle) avant de lire ce fichier.

# setting NOM [défaut] : la valeur de l'environnement, sinon celle de deploy/.env, sinon le
# défaut. deploy/.env n'est jamais exécuté par le shell : MAIL_FROM y contient des chevrons.
setting() {
  local name=$1 default=${2-} value
  if [[ -n ${!name-} ]]; then
    printf '%s\n' "${!name}"
    return
  fi
  value=$(sed -n "s/^$name=//p" "$DEPLOY_DIR/.env" 2>/dev/null | tail -n 1)
  printf '%s\n' "${value:-$default}"
}

# Le projet Compose de production (COMPOSE_PROJECT_NAME le remplace, pour un essai). Sans les
# lignes de progression de Compose : le journal d'une mise à jour se lit dans la CI.
compose() {
  docker compose --progress quiet --project-directory "$DEPLOY_DIR" \
    -f "$DEPLOY_DIR/compose.prod.yml" "$@"
}

log() {
  printf '%s  %s\n' "$(date '+%F %T')" "$*" >&2
}

fail() {
  log "ÉCHEC : $*"
  exit 1
}
