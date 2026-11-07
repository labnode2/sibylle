#!/usr/bin/env bash
# Production update. The deploy hook (deploy/webhook/hooks.yaml) runs it with the commit that
# just landed on main; it can also be run by hand:
#   deploy/update.sh [commit]            moves the repository to main (the deploy/ configuration)
#                                        and pulls the images (the server's, the web's)
#   deploy/update.sh --no-pull [commit]  keeps the images already on the machine (after a change
#                                        to deploy/.env, for instance)
# Each service gets DEPLOY_WAIT_TIMEOUT seconds (300) to report healthy.
# If nothing changed, it only makes sure everything is running. Otherwise: backup (database and
# uploaded images), restart, then wait until every service is healthy; on failure, roll back to
# the previous version (repository and images) and exit with an error, giving the command that
# would bring back the previous database if a migration ran. One update at a time: when the
# "Backend" and "Frontend" workflows both push an image, the second update brings whatever the
# first did not find yet.
# Every update, done or failed, is posted to Discord (DISCORD_WEBHOOK_URL in deploy/.env); a
# machine already up to date and healthy says nothing.
# Everything lives in functions called on the last line: the repository can change this file
# while it runs without throwing it off (bash reads a script as it goes).
set -euo pipefail

# The services whose image the CI builds: pulled, kept as `previous` and rolled back together (the
# worker runs the api's image).
IMAGE_SERVICES=(api sibylle)
# Old versions of those images, and only those, are pruned after a success.
IMAGE_SOURCE=https://github.com/labnode2/sibylle

main() {
  DEPLOY_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
  # shellcheck source=lib.sh
  . "$DEPLOY_DIR/lib.sh"
  trap 'report $?' EXIT
  local repo pull=1 commit= arg
  repo=$(cd "$DEPLOY_DIR/.." && pwd)
  for arg in "$@"; do
    case $arg in
      --no-pull) pull=0 ;;
      *) commit=$arg ;;
    esac
  done
  WAIT_TIMEOUT=$(setting DEPLOY_WAIT_TIMEOUT 300)
  [[ -z $commit || $commit =~ ^[0-9a-f]{40}$ ]] || fail "invalid commit: $commit"

  exec 9>"$DEPLOY_DIR/.deploy.lock"
  if ! flock --nonblock 9; then
    log "Another update is running: waiting for it to finish."
    flock --wait 900 9 || fail "the other update does not finish"
  fi

  local old_rev service
  local -A old_ref=() old_image=()
  old_rev=$(git -C "$repo" rev-parse HEAD)
  for service in "${IMAGE_SERVICES[@]}"; do
    old_ref[$service]=$(image_ref "$service") || fail "cannot read deploy/compose.prod.yml or deploy/.env"
    old_image[$service]=$(running_image "$service")
  done

  log "Repository: main from $(git -C "$repo" remote get-url origin)"
  git -C "$repo" fetch --quiet origin main || fail "cannot fetch main from GitHub"
  if [[ -n $commit ]] && ! git -C "$repo" merge-base --is-ancestor "$commit" origin/main 2>/dev/null; then
    fail "commit $commit is not on main"
  fi
  git -C "$repo" checkout --quiet --detach origin/main ||
    fail "the repository in $repo has local changes"
  theme_readable "$repo"
  local new_rev
  local -A new_ref=() new_image=()
  new_rev=$(git -C "$repo" rev-parse HEAD)
  for service in "${IMAGE_SERVICES[@]}"; do
    new_ref[$service]=$(image_ref "$service") || fail "cannot read deploy/compose.prod.yml or deploy/.env"
  done
  if ((pull)); then
    log "Images: ${new_ref[*]}"
    compose pull --quiet "${IMAGE_SERVICES[@]}" || fail "cannot pull ${new_ref[*]}"
  fi
  # The images that change, for the log and for Discord.
  local moves=() moves_md=()
  for service in "${IMAGE_SERVICES[@]}"; do
    new_image[$service]=$(image_id "${new_ref[$service]}")
    [[ -n ${new_image[$service]} ]] || fail "image ${new_ref[$service]} is not on the machine"
    if [[ ${new_image[$service]} != "${old_image[$service]}" ]]; then
      moves+=("$service $(short "${old_image[$service]}") -> $(short "${new_image[$service]}")")
      moves_md+=("$service \`$(short "${old_image[$service]}")\` → \`$(short "${new_image[$service]}")\`")
    fi
  done

  if [[ $new_rev == "$old_rev" && ${#moves[@]} -eq 0 ]]; then
    log "Already up to date ($(short "$new_rev"), same images): checking that everything runs."
    if ! compose up -d --remove-orphans --wait --wait-timeout "$WAIT_TIMEOUT"; then
      DETAILS=$'\n'$(services)
      fail "a service is not healthy"
    fi
    return
  fi

  local backup= changes
  if [[ -n $(compose ps --quiet --status running db) ]]; then
    backup=$("$DEPLOY_DIR/backup/backup.sh" pre-deploy) || fail "the backup failed: nothing changed"
  else
    log "The database is not running yet: no backup."
  fi
  # The images to give back their name if the update fails, the one before kept as `previous`.
  local retag=()
  for service in "${IMAGE_SERVICES[@]}"; do
    [[ -n ${old_image[$service]} ]] || continue
    if [[ -z $(image_id "${old_image[$service]}") ]]; then
      log "The image $service ran ($(short "${old_image[$service]}")) is no longer on the machine: no rollback for it."
      continue
    fi
    retag+=("${old_image[$service]}" "${old_ref[$service]}")
    if [[ ${old_image[$service]} != "${new_image[$service]}" ]]; then
      docker tag "${old_image[$service]}" "${old_ref[$service]%:*}:previous"
    fi
  done

  log "Restart: $(short "$old_rev") -> $(short "$new_rev"), images: $(join "${moves[@]:-unchanged}")"
  if compose up -d --remove-orphans --wait --wait-timeout "$WAIT_TIMEOUT"; then
    docker image prune --force --filter "label=org.opencontainers.image.source=$IMAGE_SOURCE" >/dev/null
    log "Deployed: $(short "$new_rev"), every service is healthy."
    SUMMARY="✅ Sibylle deployed: \`$(short "$old_rev")\` → \`$(short "$new_rev")\`"
    ((${#moves_md[@]} == 0)) || SUMMARY+=", images: $(join "${moves_md[@]}")"
    SUMMARY+=", every service is healthy."
    changes=$(git -C "$repo" log --max-count 10 --format='• `%h` %s' "$old_rev..$new_rev")
    [[ -z $changes ]] || SUMMARY+=$'\n'$changes
    return
  fi

  log "A service is not healthy:"
  compose ps --all >&2
  compose logs --no-color --tail 30 api worker sibylle >&2
  DETAILS=$'\n'$(services)
  rollback "$repo" "$old_rev" "${retag[@]}"
  if [[ -n $backup ]]; then
    log "If a migration ran, the previous database is in $backup:"
    log "  $DEPLOY_DIR/backup/restore.sh --yes $backup"
    DETAILS+=$'\n'"If a migration ran: \`$DEPLOY_DIR/backup/restore.sh --yes $backup\`"
  fi
  fail "update to $(short "$new_rev") rolled back"
}

# rollback REPO REV [IMAGE REF]...: back to the commit REV, each IMAGE under the REF the previous
# configuration asks for.
rollback() {
  local repo=$1 rev=$2 outcome
  shift 2
  log "Rolling back to the previous version ($(short "$rev"))"
  git -C "$repo" checkout --quiet --detach "$rev"
  theme_readable "$repo"
  while (($#)); do
    docker tag "$1" "$2" || log "Cannot give $2 back its previous image."
    shift 2
  done
  if compose up -d --remove-orphans --wait --wait-timeout "$WAIT_TIMEOUT"; then
    outcome="Previous version ($(short "$rev")) restored."
  else
    outcome="The previous version does not come back either: manual action needed."
  fi
  log "$outcome"
  DETAILS+=$'\n'$outcome
}

# theme_readable REPO: Keycloak (labnode2/docker) mounts keycloak/theme read-only and reads it as
# its own user, not sibylle. Whatever umask the checkout ran with, the theme stays readable by
# everyone: its pages, styles and fonts are what every browser gets anyway.
theme_readable() {
  [[ ! -d $1/keycloak/theme ]] || chmod -R a+rX "$1/keycloak/theme" ||
    log "Cannot make keycloak/theme readable: Keycloak may not see Sibylle's theme."
}

# The state of each service, one line each, for Discord.
services() {
  compose ps --all --format '• {{.Service}}: {{.Status}}'
}

# The final Discord message, from SUMMARY (a successful deploy) or FAILURE (lib.sh) and DETAILS
# (the state of the services, the rollback).
report() {
  if (($1 == 0)); then
    [[ -z ${SUMMARY-} ]] || notify "$SUMMARY"
  else
    notify "❌ Sibylle: ${FAILURE:-update interrupted (code $1)}.${DETAILS-}"
  fi
}

# The image a service runs, from the configuration as it stands: nothing for a service it does not
# have yet. (`config --images sibylle` would also give the images of the services it depends on.)
image_ref() {
  compose config --format json | jq --raw-output --arg service "$1" '.services[$service].image // empty'
}

# The arguments joined with ", ".
join() {
  local joined
  joined=$(printf '%s, ' "$@")
  printf '%s\n' "${joined%, }"
}

image_id() {
  docker image inspect --format '{{.Id}}' "$1" 2>/dev/null || true
}

# The image the container of a service runs, none before its first start. Not the tag's: a pull
# may have moved it since (an update that failed after pulling, a pull by hand).
running_image() {
  local container
  container=$(compose ps --all --format '{{.Service}} {{.ID}}' | awk -v service="$1" '$1 == service { print $2; exit }')
  [[ -z $container ]] || docker inspect --format '{{.Image}}' "$container"
}

# The first 7 characters of a commit or an image (without "sha256:").
short() {
  local id=${1#sha256:}
  if [[ -n $id ]]; then
    printf '%s\n' "${id:0:7}"
  else
    printf 'none\n'
  fi
}

main "$@"
exit
