#!/usr/bin/env bash
# Production update. The deploy hook (deploy/webhook/hooks.yaml) runs it with the commit that
# just landed on main; it can also be run by hand:
#   deploy/update.sh [commit]            moves the repository to main (the deploy/ configuration)
#                                        and pulls the images
#   deploy/update.sh --no-pull [commit]  keeps the images already on the machine (after a change
#                                        to deploy/.env, for instance)
# Each service gets DEPLOY_WAIT_TIMEOUT seconds (300) to report healthy.
# If nothing changed, it only makes sure everything is running. Otherwise: backup (database and
# uploaded images), restart, then wait until every service is healthy; on failure, roll back to
# the previous version (repository and images) and exit with an error, giving the command that
# would bring back the previous database if a migration ran. One update at a time.
# Every update, done or failed, is posted to Discord (DISCORD_WEBHOOK_URL in deploy/.env); a
# machine already up to date and healthy says nothing.
# Everything lives in functions called on the last line: the repository can change this file
# while it runs without throwing it off (bash reads a script as it goes).
set -euo pipefail

# Old versions of the server image, and only those, are pruned after a success.
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

  local old_rev old_ref old_image
  old_rev=$(git -C "$repo" rev-parse HEAD)
  old_ref=$(api_image) || fail "cannot read deploy/compose.prod.yml or deploy/.env"
  old_image=$(image_id "$old_ref")

  log "Repository: main from $(git -C "$repo" remote get-url origin)"
  git -C "$repo" fetch --quiet origin main || fail "cannot fetch main from GitHub"
  if [[ -n $commit ]] && ! git -C "$repo" merge-base --is-ancestor "$commit" origin/main 2>/dev/null; then
    fail "commit $commit is not on main"
  fi
  git -C "$repo" checkout --quiet --detach origin/main ||
    fail "the repository in $repo has local changes"
  local new_rev new_ref new_image
  new_rev=$(git -C "$repo" rev-parse HEAD)
  new_ref=$(api_image) || fail "cannot read deploy/compose.prod.yml or deploy/.env"
  if ((pull)); then
    log "Images: $new_ref"
    compose pull --quiet api worker || fail "cannot pull $new_ref"
  fi
  new_image=$(image_id "$new_ref")
  [[ -n $new_image ]] || fail "image $new_ref is not on the machine"

  if [[ $new_rev == "$old_rev" && $new_image == "$old_image" ]]; then
    log "Already up to date ($(short "$new_rev"), image $(short "$new_image")): checking that everything runs."
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
  if [[ -n $old_image && $old_image != "$new_image" ]]; then
    docker tag "$old_image" "${old_ref%:*}:previous"
  fi

  log "Restart: $(short "$old_rev") -> $(short "$new_rev"), image $(short "$old_image") -> $(short "$new_image")"
  if compose up -d --remove-orphans --wait --wait-timeout "$WAIT_TIMEOUT"; then
    docker image prune --force --filter "label=org.opencontainers.image.source=$IMAGE_SOURCE" >/dev/null
    log "Deployed: $(short "$new_rev"), every service is healthy."
    SUMMARY="✅ Sibylle deployed: \`$(short "$old_rev")\` → \`$(short "$new_rev")\`"
    if [[ $old_image != "$new_image" ]]; then
      SUMMARY+=", image \`$(short "$old_image")\` → \`$(short "$new_image")\`"
    fi
    SUMMARY+=", every service is healthy."
    changes=$(git -C "$repo" log --max-count 10 --format='• `%h` %s' "$old_rev..$new_rev")
    [[ -z $changes ]] || SUMMARY+=$'\n'$changes
    return
  fi

  log "A service is not healthy:"
  compose ps --all >&2
  compose logs --no-color --tail 30 api worker >&2
  DETAILS=$'\n'$(services)
  rollback "$repo" "$old_rev" "$old_ref" "$old_image"
  if [[ -n $backup ]]; then
    log "If a migration ran, the previous database is in $backup:"
    log "  $DEPLOY_DIR/backup/restore.sh --yes $backup"
    DETAILS+=$'\n'"If a migration ran: \`$DEPLOY_DIR/backup/restore.sh --yes $backup\`"
  fi
  fail "update to $(short "$new_rev") rolled back"
}

rollback() {
  local repo=$1 rev=$2 ref=$3 image=$4 outcome
  log "Rolling back to the previous version ($(short "$rev"))"
  git -C "$repo" checkout --quiet --detach "$rev"
  if [[ -n $image ]]; then
    docker tag "$image" "$ref"
  fi
  if compose up -d --remove-orphans --wait --wait-timeout "$WAIT_TIMEOUT"; then
    outcome="Previous version ($(short "$rev")) restored."
  else
    outcome="The previous version does not come back either: manual action needed."
  fi
  log "$outcome"
  DETAILS+=$'\n'$outcome
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

# The image of the api service (`config --images api` would also give the database's, which it
# depends on).
api_image() {
  compose config --format json | jq --exit-status --raw-output '.services.api.image'
}

image_id() {
  docker image inspect --format '{{.Id}}' "$1" 2>/dev/null || true
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
