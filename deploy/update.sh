#!/usr/bin/env bash
# Mise à jour de la production. Le crochet de déploiement (deploy/webhook/hooks.yaml) le lance
# avec le commit qui vient d'arriver sur main ; on peut aussi le lancer à la main :
#   deploy/update.sh [commit]            met le dépôt sur main (la configuration de deploy/) et
#                                        tire les images
#   deploy/update.sh --no-pull [commit]  garde les images de la machine (après un changement de
#                                        deploy/.env, par exemple)
# Chaque service a DEPLOY_WAIT_TIMEOUT secondes (300) pour se dire en bonne santé.
# Si rien n'a changé, il s'assure seulement que tout tourne. Sinon : sauvegarde (base et images
# envoyées), redémarrage, puis attente que chaque service soit en bonne santé ; en cas d'échec,
# retour à la version précédente (dépôt et images) et sortie en erreur, avec la commande qui
# remettrait la base d'avant si une migration est passée. Une seule mise à jour à la fois.
# Tout tient dans des fonctions appelées à la dernière ligne : le dépôt peut changer ce fichier
# pendant qu'il tourne sans le dérégler (bash lit un script au fil de l'eau).
set -euo pipefail

# Les anciennes versions de l'image du serveur, et elles seules, sont nettoyées après un succès.
IMAGE_SOURCE=https://github.com/labnode2/sibylle

main() {
  DEPLOY_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
  # shellcheck source=lib.sh
  . "$DEPLOY_DIR/lib.sh"
  local repo pull=1 commit= arg
  repo=$(cd "$DEPLOY_DIR/.." && pwd)
  for arg in "$@"; do
    case $arg in
      --no-pull) pull=0 ;;
      *) commit=$arg ;;
    esac
  done
  WAIT_TIMEOUT=$(setting DEPLOY_WAIT_TIMEOUT 300)
  [[ -z $commit || $commit =~ ^[0-9a-f]{40}$ ]] || fail "commit invalide : $commit"

  exec 9>"$DEPLOY_DIR/.deploy.lock"
  if ! flock --nonblock 9; then
    log "Une autre mise à jour est en cours : j'attends qu'elle finisse."
    flock --wait 900 9 || fail "l'autre mise à jour ne finit pas"
  fi

  local old_rev old_ref old_image
  old_rev=$(git -C "$repo" rev-parse HEAD)
  old_ref=$(api_image) || fail "deploy/compose.prod.yml ou deploy/.env illisible"
  old_image=$(image_id "$old_ref")

  log "Dépôt : main de $(git -C "$repo" remote get-url origin)"
  git -C "$repo" fetch --quiet origin main || fail "impossible de lire main sur GitHub"
  if [[ -n $commit ]] && ! git -C "$repo" merge-base --is-ancestor "$commit" origin/main 2>/dev/null; then
    fail "le commit $commit n'est pas sur main"
  fi
  git -C "$repo" checkout --quiet --detach origin/main ||
    fail "le dépôt de $repo a des modifications locales"
  local new_rev new_ref new_image
  new_rev=$(git -C "$repo" rev-parse HEAD)
  new_ref=$(api_image) || fail "deploy/compose.prod.yml ou deploy/.env illisible"
  if ((pull)); then
    log "Images : $new_ref"
    compose pull --quiet api worker || fail "impossible de tirer $new_ref"
  fi
  new_image=$(image_id "$new_ref")
  [[ -n $new_image ]] || fail "l'image $new_ref n'est pas sur la machine"

  if [[ $new_rev == "$old_rev" && $new_image == "$old_image" ]]; then
    log "Déjà à jour ($(short "$new_rev"), image $(short "$new_image")) : je vérifie que tout tourne."
    compose up -d --remove-orphans --wait --wait-timeout "$WAIT_TIMEOUT" ||
      fail "un service n'est pas en bonne santé"
    return
  fi

  local backup=
  if [[ -n $(compose ps --quiet --status running db) ]]; then
    backup=$("$DEPLOY_DIR/backup/backup.sh" pre-deploy) || fail "la sauvegarde a échoué : rien n'a changé"
  else
    log "La base ne tourne pas encore : pas de sauvegarde."
  fi
  if [[ -n $old_image && $old_image != "$new_image" ]]; then
    docker tag "$old_image" "${old_ref%:*}:previous"
  fi

  log "Redémarrage : $(short "$old_rev") -> $(short "$new_rev"), image $(short "$old_image") -> $(short "$new_image")"
  if compose up -d --remove-orphans --wait --wait-timeout "$WAIT_TIMEOUT"; then
    docker image prune --force --filter "label=org.opencontainers.image.source=$IMAGE_SOURCE" >/dev/null
    log "Déployé : $(short "$new_rev"), tous les services sont en bonne santé."
    return
  fi

  log "Un service n'est pas en bonne santé :"
  compose ps --all >&2
  compose logs --no-color --tail 30 api worker >&2
  rollback "$repo" "$old_rev" "$old_ref" "$old_image"
  if [[ -n $backup ]]; then
    log "Si une migration est passée, la base d'avant est dans $backup :"
    log "  $DEPLOY_DIR/backup/restore.sh --yes $backup"
  fi
  fail "mise à jour vers $(short "$new_rev") annulée"
}

rollback() {
  local repo=$1 rev=$2 ref=$3 image=$4
  log "Retour à la version précédente ($(short "$rev"))"
  git -C "$repo" checkout --quiet --detach "$rev"
  if [[ -n $image ]]; then
    docker tag "$image" "$ref"
  fi
  if compose up -d --remove-orphans --wait --wait-timeout "$WAIT_TIMEOUT"; then
    log "Version précédente rétablie."
  else
    log "La version précédente ne repart pas non plus : il faut intervenir à la main."
  fi
}

# L'image du service api (`config --images api` donnerait aussi celle de la base, dont il dépend).
api_image() {
  compose config --format json | jq --exit-status --raw-output '.services.api.image'
}

image_id() {
  docker image inspect --format '{{.Id}}' "$1" 2>/dev/null || true
}

# Les 7 premiers caractères d'un commit ou d'une image (sans « sha256: »).
short() {
  local id=${1#sha256:}
  if [[ -n $id ]]; then
    printf '%s\n' "${id:0:7}"
  else
    printf 'aucune\n'
  fi
}

main "$@"
exit
