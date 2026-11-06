# Going to production

Production runs on dev-external, the labnode VM, behind its reverse proxy, Nginx Proxy Manager
(NPM). It lives apart from the VM's other applications: a clone of the repository in
`/opt/sibylle`, a Compose project `sibylle-prod` (`deploy/compose.prod.yml`), a system user
`sibylle`, and its data in `/mnt/data/sibylle`.

Visitors reach `sibylle.cc` through Cloudflare's proxy, which connects to the box's port 443; the
box forwards it to the VM, where NPM terminates TLS and forwards to `http://sibylle:8443` over the
VM's `proxy` network. `sibylle` is the nginx container (`deploy/nginx/`): it serves the
interface, and relays `/api/` to the `api` service and `/hooks/` to webhook on the VM. No port is
published.

The VM's own rules apply (its `CLAUDE.md` and Docker network guide, in the labnode2/docker
repository): read-only containers without privileges and with limits, a UID per application,
nothing on `proxy` but what NPM must reach. The `api` and the `worker` reach the Internet
(Brevo's SMTP, push notifications) through a network of their own; the `db` reaches nothing. The
VM cannot reach the local network, and Sibylle needs nothing there.

## How an update arrives

1. A push to `main` starts the “Backend” workflow when the server changed (ruff, mypy, pytest,
   then the image `registry.labnode.ovh/sibylle/backend`), the “Frontend” workflow when the
   interface or `deploy/nginx/` changed (Prettier, ESLint, TypeScript, Vitest, then the image
   `registry.labnode.ovh/sibylle/web`: the interface served by nginx), or both. Each image is
   tagged `main` and `sha-<commit>`.
2. Each workflow that pushed an image runs the “Deploy” job (`.github/workflows/deploy.yml`),
   which calls `https://sibylle.cc/hooks/deploy` with the commit and an id specific to the job
   attempt, signed (HMAC-SHA256 of the body, with the shared secret).
3. NPM, then nginx, relay the request to webhook, which runs on the VM (service
   `sibylle-webhook`); webhook checks the signature, answers 202 at once and starts in the
   background `deploy/webhook/deploy.sh <id> <commit>`, which runs `deploy/update.sh <commit>`.
   Cloudflare cuts a response that takes more than 100 s: the CI cannot wait for the end of the
   update on the same request.
4. `update.sh` moves `/opt/sibylle` to `main`, pulls both images, backs up the database and the
   uploaded images, restarts what changed, then waits until every service is healthy. If one is
   not, it rolls back to the previous version (commit and images) and says so. Its log is
   written to `/opt/sibylle/deploy-logs/<id>.log` (kept 30 days), and the Discord channel gets
   the outcome.
5. The job polls `https://sibylle.cc/hooks/deploy-status` every 10 s, shows the log as it goes
   and ends green or red with the update. It goes through nginx, which the update may restart:
   it keeps polling for 6 minutes without an answer before it gives up (the update itself goes
   on, and Discord still gets the outcome).

One update runs at a time; when both workflows push an image, the second update brings what the
first did not find yet. A badly signed request, or one for a commit that is not on `main`,
starts nothing.

## 1. Prepare the VM (once)

What needs root on the VM goes into the `setup.sh` of labnode2/docker, so that a fresh VM gets
the same result. That script already creates the `proxy` network; for Sibylle it also needs:

```bash
# The data: the database at UID 2005 (the VM's UID for Sibylle, the next one in its CLAUDE.md),
# the uploaded images at UID 10001 (the server image's own user), on a volume of their own
# (size to choose) since visitors fill it.
install -d -m 755 "$DATA/sibylle"
install -d -m 700 -o 2005 -g 2005 "$DATA/sibylle/db"
make_lv sibylle 10G "$DATA/sibylle/uploads"
chown 10001:10001 "$DATA/sibylle/uploads" && chmod 700 "$DATA/sibylle/uploads"
# The deploy hooks (section 4): nginx, in its container, reaches webhook on docker0.
ufw allow in from 172.30.0.0/16 to 172.30.0.1 port 9000 proto tcp comment 'sibylle deploy hooks'
```

Sibylle stays out of the script's `APPS` list: `update.sh` starts it. Its row in the
`CLAUDE.md` application table: UID 2005 (db) and 10001 (api, worker), data in
`/mnt/data/sibylle`, NPM forwards to `http://sibylle:8443`.

Then, on the VM:

```bash
sudo apt install webhook jq curl git
sudo useradd --system --create-home --home-dir /var/lib/sibylle --shell /usr/sbin/nologin --groups docker sibylle
sudo install -d -o sibylle -g sibylle /opt/sibylle
sudo -u sibylle git clone https://github.com/labnode2/sibylle.git /opt/sibylle
sudo -u sibylle -H docker login registry.labnode.ovh
```

The `docker` group is worth root on the VM: `sibylle` does nothing but run production, through
`update.sh` and webhook. The registry does not tell reading from writing apart: a separate
account for the VM can be removed without touching the CI's.

## 2. Production settings

```bash
sudo -u sibylle cp /opt/sibylle/deploy/.env.example /opt/sibylle/deploy/.env
sudo -u sibylle chmod 600 /opt/sibylle/deploy/.env
sudo -u sibylle -H docker run --rm registry.labnode.ovh/sibylle/backend:main gen-secrets
sudo -u sibylle -e /opt/sibylle/deploy/.env
```

In `.env`: `ENVIRONMENT=production`, `PUBLIC_ORIGIN=https://sibylle.cc`, the three secrets
printed by `gen-secrets` (`POSTGRES_PASSWORD`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`), Brevo's
e-mail settings (`SMTP_*`, `MAIL_FROM`) and `VAPID_SUBJECT`. `DATABASE_URL` and `UPLOAD_DIR` are
set by the Compose file; nginx also takes the site's domain from `PUBLIC_ORIGIN`. The
production-only settings (tags, data folder, backups, logs) are described at the end of
`.env.example`.

For Discord to get every update, done or failed: in the chosen channel, *Edit Channel →
Integrations → Webhooks → New Webhook*, copy its URL and put it in `.env` as
`DISCORD_WEBHOOK_URL`. The URL is enough to write to the channel: it stays in `.env`, like a
secret. A VM already up to date and healthy posts nothing; a failed post is logged without
stopping the update.

## 3. First start

```bash
sudo -u sibylle -H /opt/sibylle/deploy/update.sh
sudo -u sibylle -H docker compose --project-directory /opt/sibylle/deploy -f /opt/sibylle/deploy/compose.prod.yml ps
```

`db`, `api`, `worker` and `sibylle` must be `healthy`, with an empty ports column. Until NPM
forwards the site (section 6), nothing reaches nginx from the Internet. A check on the VM, the way
NPM reaches it:

```bash
sudo docker exec npm curl -s -H 'Host: sibylle.cc' http://sibylle:8443/api/health
```

## 4. The deploy hooks

A 64-character secret, readable by root only:

```bash
sudo install -d -m 700 /etc/sibylle
sudo sh -c 'umask 077; printf "SIBYLLE_WEBHOOK_SECRET=%s\n" "$(openssl rand -hex 32)" > /etc/sibylle/webhook.env'
```

The services, copied (not linked) so that the unit files stay owned by root:

```bash
sudo cp /opt/sibylle/deploy/systemd/sibylle-webhook.service /opt/sibylle/deploy/systemd/sibylle-backup.service /opt/sibylle/deploy/systemd/sibylle-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sibylle-webhook.service sibylle-backup.timer
```

webhook listens on `172.30.0.1:9000`, the address of the VM's Docker bridge
(`ip -4 addr show docker0`): nginx reaches it from its container (`location /hooks/`, POST
only), through the ufw rule of section 1; the Internet never reaches it directly. A trial on the
VM, signed the way the CI does it, with the id `trial-1`:

```bash
secret=$(sudo sed -n 's/^SIBYLLE_WEBHOOK_SECRET=//p' /etc/sibylle/webhook.env)
hook() {
  signature=$(printf '%s' "$2" | openssl dgst -sha256 -hmac "$secret" | awk '{print $NF}')
  curl -sS -H "Content-Type: application/json" -H "X-Hub-Signature-256: sha256=$signature" \
    --data-binary "$2" "http://172.30.0.1:9000/hooks/$1"
}
hook deploy "{\"id\":\"trial-1\",\"commit\":\"$(git -C /opt/sibylle rev-parse origin/main)\"}"
hook deploy-status '{"id":"trial-1"}'
```

`deploy` answers “Update started.” (202); `deploy-status` answers `state=running`, then
`state=success` or `state=failure`, followed by the log of `update.sh` (“Already up to date…”),
or `state=unknown` for an unknown id. webhook's answers: 403 without a signature or for a
malformed commit or id, 500 with “Error occurred while evaluating hook rules” for a wrong
signature. Service log: `journalctl -u sibylle-webhook`.

## 5. Cloudflare and the certificate

In Cloudflare's dashboard, for `sibylle.cc`:

- *DNS*: an `A` record for `sibylle.cc` to the box's public address, the one the VM's other
  sites already use, **proxied**; no `AAAA` record (IPv6 has no NAT: the box's forwarding would
  not apply);
- *SSL/TLS → Overview*: **Full (strict)**; *Edge Certificates*: **Always Use HTTPS**;
- *SSL/TLS → Origin Server → Create Certificate*: hostnames `sibylle.cc` and `*.sibylle.cc`. Keep
  the certificate and the private key for NPM (section 6): the key is shown only once. Valid 15
  years, it leaves nothing to renew and no challenge to get through Cloudflare's proxy.

The box's public address is the site's origin: Cloudflare hides it from `sibylle.cc`'s DNS
answers, but a VM site whose record is not proxied gives it away, and anyone who knows it reaches
NPM directly. Authenticated Origin Pulls (section 6) then lets in Cloudflare alone. If the box's
public address changes from time to time, the `A` record has to follow it (a dynamic DNS client
for Cloudflare); nothing here does it.

## 6. NPM

In NPM's admin interface (through the SSH tunnel of the VM's guide), first *SSL Certificates →
Add SSL Certificate → Custom*: the origin certificate and its key from section 5. Then *Hosts →
Proxy Hosts → Add Proxy Host*:

- *Details*: domain name `sibylle.cc`; scheme `http`, forward hostname `sibylle`, forward port
  `8443`; **Websockets Support** on (the live updates, `/api/ws`); **Block Common Exploits** on;
- *SSL*: the custom certificate above; **Force SSL** and **HTTP/2 Support** on; **HSTS** off:
  Sibylle sends its own header (`deploy/nginx/templates/sibylle/headers.inc.template`), and NPM
  would add a second one;
- *Advanced*: Authenticated Origin Pulls, recommended. Copy `deploy/npm/origin-pull-ca.pem`
  (Cloudflare's certificate authority for it, valid until November 2029) into NPM's data folder,
  the one mounted on `/data` in its container, as `sibylle/origin-pull-ca.pem`, then:

```nginx
ssl_client_certificate /data/sibylle/origin-pull-ca.pem;
ssl_verify_client on;
```

Turn on *SSL/TLS → Origin Server → Authenticated Origin Pulls* in Cloudflare first: once these
lines are in, NPM refuses, for `sibylle.cc`, any connection that does not show Cloudflare's client
certificate. Without them, someone who reaches NPM directly can also set the `CF-Connecting-IP`
header, which nginx takes as the visitor's address (rate limits).

Then `https://sibylle.cc/api/health` answers `{"status":"ok","db":"ok"}` from anywhere.

## 7. GitHub

In the repository's *Settings → Secrets and variables → Actions*:

- `REGISTRY_USERNAME` and `REGISTRY_PASSWORD`: the CI's account on the registry;
- `DEPLOY_WEBHOOK_SECRET`: the value from `/etc/sibylle/webhook.env`. To set once
  `https://sibylle.cc/hooks/` answers (sections 5 and 6); until then, the “Deploy” job warns and
  stops there. It can live in the `production` environment (*Settings → Environments*), which
  also keeps the deployment history and can require an approval.

The `DEPLOY_HOOKS_URL` variable replaces `https://sibylle.cc/hooks` when needed, under which the
CI calls `deploy` and `deploy-status`. *Actions → Deploy → Run workflow* redeploys `main` by
hand, for instance after a change to `deploy/compose.prod.yml` alone, which builds no image.

## 8. Backups and restore

`deploy/backup/backup.sh` backs up the database (`pg_dump` in custom format) and the uploaded
images to `/opt/sibylle/backups`, every night around 3:30 (`sibylle-backup.timer`) and before
each update; 14 days are kept. `sudo systemctl start sibylle-backup` makes one right away.

Restore a backup (the API and the worker stop while it runs):

```bash
sudo -u sibylle -H /opt/sibylle/deploy/backup/restore.sh --yes \
  /opt/sibylle/backups/sibylle-YYYYMMDD-HHMMSS-nightly.dump \
  /opt/sibylle/backups/sibylle-YYYYMMDD-HHMMSS-nightly.uploads.tar.gz
```

Encrypted copy on the VPS, every night: install `age`, create the key pair somewhere other than
the VM (`age-keygen`, the private key stays offline), authorize the SSH key of `sibylle`
(`sudo -u sibylle -H ssh-keygen -t ed25519`) on the VPS, then set in `.env`
`BACKUP_AGE_RECIPIENT` (the public key) and `BACKUP_REMOTE` (the rsync destination). The VPS
keeps its copies as long as decided on its side.

## Day to day

- Deploy the latest `main` by hand: `sudo -u sibylle -H /opt/sibylle/deploy/update.sh`.
- Apply a change to `.env` without pulling an image: `update.sh --no-pull`.
- Go back to a given version: `SIBYLLE_BACKEND_TAG=sha-<commit>` (the server) or
  `SIBYLLE_WEB_TAG=sha-<commit>` (the interface) in `.env`, then `update.sh`; the commit must be
  one that built that image. Remove the line to follow `main` again. The images from before the
  last update also stay on the VM, tagged `previous`.
- If a migration ran before a failure, `update.sh` gives the `restore.sh` command that brings
  back the database from before the update.
- Read again an update started by the CI: `/opt/sibylle/deploy-logs/<run>-<attempt>.log`, from
  the GitHub run id and the attempt number.

## Still missing

- Brevo's SPF, DKIM and DMARC records for `sibylle.cc`, and a restore rehearsed on a test
  database before the launch (T145).
