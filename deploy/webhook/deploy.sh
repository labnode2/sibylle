#!/usr/bin/env bash
# Started in the background by the `deploy` hook (hooks.yaml), which has already answered the
# CI: deploy/update.sh runs here, its log in <DEPLOY_LOG_DIR>/<id>.log, then its exit code in
# <id>.status, which the `deploy-status` hook (status.sh) returns to the CI.
#   deploy/webhook/deploy.sh <id> <commit>
# Like update.sh, everything lives in a function: the update can change this file.
set -euo pipefail

main() {
  DEPLOY_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
  # shellcheck source=../lib.sh
  . "$DEPLOY_DIR/lib.sh"

  local id=${1-} commit=${2-} dir status=0
  [[ $id =~ ^[0-9a-z][0-9a-z-]{0,63}$ ]] || fail "invalid id: $id"
  dir=$(deploy_log_dir)
  umask 027
  mkdir -p "$dir"
  find "$dir" -maxdepth 1 -type f \( -name '*.log' -o -name '*.status' \) -mtime +30 -delete
  rm -f "$dir/$id.status"
  "$DEPLOY_DIR/update.sh" "$commit" >"$dir/$id.log" 2>&1 || status=$?
  printf '%s\n' "$status" >"$dir/$id.status.part"
  mv "$dir/$id.status.part" "$dir/$id.status"
}

main "$@"
exit
