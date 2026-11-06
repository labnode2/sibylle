#!/usr/bin/env bash
# Run by the `deploy-status` hook (hooks.yaml): where the update <id> started by deploy.sh
# stands. The first line gives the state, `state=running`, `state=success`, `state=failure` or
# `state=unknown` (nothing under that id), and the log follows.
#   deploy/webhook/status.sh <id>
set -euo pipefail

main() {
  DEPLOY_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
  # shellcheck source=../lib.sh
  . "$DEPLOY_DIR/lib.sh"

  local id=${1-} dir
  [[ $id =~ ^[0-9a-z][0-9a-z-]{0,63}$ ]] || fail "invalid id: $id"
  dir=$(deploy_log_dir)
  if [[ -f $dir/$id.status ]]; then
    if [[ $(<"$dir/$id.status") == 0 ]]; then
      echo state=success
    else
      echo state=failure
    fi
  elif [[ -f $dir/$id.log ]]; then
    echo state=running
  else
    echo state=unknown
    return
  fi
  cat "$dir/$id.log"
}

main "$@"
exit
