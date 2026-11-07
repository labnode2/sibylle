# Sibylle's realm (OpenTofu)

The realm `sibylle` and the app's client `sibylle`, in production's Keycloak (labnode2/docker,
`dev-external/keycloak`). The realm's settings are those of `../dev-realm.json`, the local
Keycloak's ("What the realm sets" in `../README.md`): change both together.

- `main.tf`: the realm (French, the `sibylle` theme, sign-up by e-mail, forgotten password, no
  blocking address check, `length(8)`, the brute-force lock of research.md R4, Brevo's SMTP)
  and the confidential client `sibylle` (authorization code with PKCE, back-channel logout),
  whose service account may manage the realm's users and nothing else.
- `variables.tf`: production's values by default; the SMTP login and key come from the
  environment.
- `outputs.tf`: the issuer, the client's id and its secret, for the app's settings.
- `tofu.sh`: OpenTofu in Docker, nothing to install.

## Where it runs

On dev-external only, in the VM's copy of the repository (`/opt/sibylle`), as `sibylle`: the
state and the secrets live there, whatever PC starts it. `tofu.sh` refuses to run anywhere else,
where it would start a second state knowing nothing of the first (`TOFU_ELSEWHERE=1` lets a
trial run against another Keycloak). On the VM, it finds:

- Keycloak's admin port on `127.0.0.1:8180`, with no tunnel;
- the `terraform` client's secret in `keycloak/terraform/.env` (mode 600, out of Git);
- Brevo's SMTP login and key in the app's `deploy/.env` (`SMTP_USER`, `SMTP_PASSWORD`).

The code it applies is the VM's copy, so `main` as deployed: commit and push a change, let the
deployment move `/opt/sibylle` (the "Keycloak theme" workflow deploys every change under
`keycloak/`), then plan and apply.

## The `terraform` client

OpenTofu signs in to Keycloak as the master realm's `terraform` client. In the admin console,
through the tunnel (`ssh -L 8180:127.0.0.1:8180 dev@192.168.71.7`, http://localhost:8180/admin/),
realm `master`:

1. Clients, Create client: Client ID `terraform`. Then Client authentication on, Service account
   roles on, Standard flow and Direct access grants off.
2. Its Service account roles tab: assign the realm role `admin`.
3. Its Client scopes tab: add `kc-admin-api` as a Default scope. Keycloak 26.8 only lets a token
   into the admin API with that scope's audience; without it, OpenTofu gets 401 on
   `/admin/serverinfo`.
4. Its Credentials tab: copy the client secret, then write it on the VM, once:

```bash
sudo -u sibylle -H bash -c 'umask 077; read -rsp "terraform client secret: " s; echo; printf "KEYCLOAK_CLIENT_SECRET=%s\n" "$s" > /opt/sibylle/keycloak/terraform/.env'
```

## Running it

From any PC that reaches the VM over SSH:

```bash
ssh -t dev@192.168.71.7 sudo -u sibylle -H /opt/sibylle/keycloak/terraform/tofu.sh init
ssh -t dev@192.168.71.7 sudo -u sibylle -H /opt/sibylle/keycloak/terraform/tofu.sh plan
ssh -t dev@192.168.71.7 sudo -u sibylle -H /opt/sibylle/keycloak/terraform/tofu.sh apply
```

`init` is needed once, and again after a change of provider. The sign-in page is then at
https://auth.sibylle.cc/realms/sibylle/account.

A local trial applied these files to the same Keycloak (26.8.2), and a second `plan` found no
changes.

## The state

`terraform.tfstate`, in `/opt/sibylle/keycloak/terraform/` on the VM, out of Git (`.gitignore`):
it holds the client's secret and the SMTP key, so `tofu.sh` keeps the folder to `sibylle` alone
(mode 700). It is the only record of what OpenTofu made; the VM's nightly Proxmox backup covers
it. Without it, OpenTofu would try to create the realm again; `tofu.sh import` can rebuild it
from Keycloak.

- `tofu.sh state list`: what it manages.
- `tofu.sh plan -refresh-only`: what changed in Keycloak behind its back.
- `tofu.sh output -raw client_secret`: the app's client secret, for `deploy/.env`.
