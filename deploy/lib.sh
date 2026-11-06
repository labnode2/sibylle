# Helpers shared by the production scripts (update.sh, backup/, webhook/), which set DEPLOY_DIR
# (the deploy/ folder of /opt/sibylle) before sourcing this file.

# setting NAME [default]: the value from the environment, else from deploy/.env, else the
# default. deploy/.env is never run by the shell: MAIL_FROM holds angle brackets.
setting() {
  local name=$1 default=${2-} value
  if [[ -n ${!name-} ]]; then
    printf '%s\n' "${!name}"
    return
  fi
  value=$(sed -n "s/^$name=//p" "$DEPLOY_DIR/.env" 2>/dev/null | tail -n 1)
  printf '%s\n' "${value:-$default}"
}

# The production Compose project (COMPOSE_PROJECT_NAME overrides it, for a trial). Without
# Compose's progress lines: an update's log is read in the CI.
compose() {
  docker compose --progress quiet --project-directory "$DEPLOY_DIR" \
    -f "$DEPLOY_DIR/compose.prod.yml" "$@"
}

# The logs of the updates started by the hook (webhook/deploy.sh), kept 30 days.
deploy_log_dir() {
  setting DEPLOY_LOG_DIR "$DEPLOY_DIR/../deploy-logs"
}

# notify MESSAGE: posts MESSAGE to the Discord channel of DISCORD_WEBHOOK_URL, when set. A failed
# post is logged without stopping anything.
notify() {
  local url
  url=$(setting DISCORD_WEBHOOK_URL)
  [[ -n $url ]] || return 0
  # Discord rejects a message over 2000 characters; no mention (@everyone…) goes out.
  jq --null-input --arg content "${1:0:2000}" '{content: $content, allowed_mentions: {parse: []}}' |
    curl --silent --show-error --fail --max-time 10 --output /dev/null \
      --header "Content-Type: application/json" --data-binary @- "$url" ||
    log "Discord message not sent."
}

log() {
  printf '%s  %s\n' "$(date '+%F %T')" "$*" >&2
}

# The failure reason stays in FAILURE, for an EXIT trap (update.sh posts it to Discord).
fail() {
  FAILURE=$*
  log "FAILED: $*"
  exit 1
}
