#!/usr/bin/env bash
# OpenTofu in Docker, nothing to install: keycloak/terraform/tofu.sh <command> [arguments].
# It runs on dev-external, in the VM's copy of the repository, as sibylle, so the state and the
# secrets live in one place whatever PC starts it (README.md):
#   ssh -t dev@192.168.71.7 sudo -u sibylle -H /opt/sibylle/keycloak/terraform/tofu.sh plan
# It signs in to Keycloak (127.0.0.1:8180 on the VM) as the master realm's `terraform` client,
# whose secret is in .env next to this script; Brevo's SMTP login and key come from the app's
# deploy/.env. Variables already in the environment win: KEYCLOAK_URL, KEYCLOAK_CLIENT_ID,
# KEYCLOAK_CLIENT_SECRET, TF_VAR_smtp_user and TF_VAR_smtp_password.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# Anywhere else, a second state would start, knowing nothing of the first. TOFU_ELSEWHERE=1 lets
# a trial run on another machine, against another Keycloak.
if [[ $(hostname) != dev-external && -z ${TOFU_ELSEWHERE:-} ]]; then
  echo "Run it on dev-external (README.md):" >&2
  echo "  ssh -t dev@192.168.71.7 sudo -u sibylle -H /opt/sibylle/keycloak/terraform/tofu.sh $*" >&2
  exit 1
fi

value() { # FILE KEY: the value of KEY=... in FILE
  [[ -r $1 ]] && sed -n "s/^$2=//p" "$1" | tail -1
}
if [[ -z ${KEYCLOAK_CLIENT_SECRET:-} ]]; then
  KEYCLOAK_CLIENT_SECRET=$(value .env KEYCLOAK_CLIENT_SECRET || true)
fi
# Only production's deploy/.env holds Brevo's login and key; a PC's points at Mailpit.
app_env=../../deploy/.env
if [[ $(value "$app_env" ENVIRONMENT || true) == production ]]; then
  : "${TF_VAR_smtp_user:=$(value "$app_env" SMTP_USER)}"
  : "${TF_VAR_smtp_password:=$(value "$app_env" SMTP_PASSWORD)}"
fi
export KEYCLOAK_CLIENT_SECRET TF_VAR_smtp_user TF_VAR_smtp_password

# The state holds the client's secret and the SMTP key: this folder is its owner's alone.
chmod 700 .

# The host's network, for this one command: Keycloak's admin port only listens on the VM's
# loopback.
tty=()
[[ -t 0 ]] && tty=(--tty)
exec docker run --rm --interactive "${tty[@]}" --network host \
  --user "$(id -u):$(id -g)" --env HOME=/tmp \
  --volume "$PWD:/work" --workdir /work \
  --env KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8180}" \
  --env KEYCLOAK_CLIENT_ID="${KEYCLOAK_CLIENT_ID:-terraform}" \
  --env KEYCLOAK_CLIENT_SECRET --env TF_VAR_smtp_user --env TF_VAR_smtp_password \
  ghcr.io/opentofu/opentofu:1.13.9 "$@"
