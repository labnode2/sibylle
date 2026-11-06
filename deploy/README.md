# Going to production

Production runs on the home machine, which is also the development PC. It lives apart: a clone
of the repository in `/opt/sibylle`, a Compose project `sibylle-prod` (`deploy/compose.prod.yml`)
with its own volumes and no published port, and a system user `sibylle`. Development (project
`sibylle`, database on port 5432) is never touched.

## How an update arrives

1. A push to `main` starts the “Serveur” workflow: ruff, mypy, pytest, then the image
   `registry.labnode.ovh/sibylle/backend`, tagged `main` and `sha-<commit>`.
2. The “Deploy” job calls `https://sibylle.cc/hooks/deploy` with the commit and an id specific
   to the job attempt, signed (HMAC-SHA256 of the body, with the shared secret).
3. nginx relays the request to webhook, which runs on the machine (service `sibylle-webhook`);
   webhook checks the signature, answers 202 at once and starts in the background
   `deploy/webhook/deploy.sh <id> <commit>`, which runs `deploy/update.sh <commit>`. Cloudflare
   cuts a response that takes more than 100 s: the CI cannot wait for the end of the update on
   the same request.
4. `update.sh` moves `/opt/sibylle` to `main`, pulls the image, backs up the database and the
   uploaded images, restarts, then waits until every service is healthy. If one is not, it rolls
   back to the previous version and says so. Its log is written to
   `/opt/sibylle/deploy-logs/<id>.log` (kept 30 days), and the Discord channel gets the outcome.
5. The job polls `https://sibylle.cc/hooks/deploy-status` every 10 s, shows the log as it goes
   and ends green or red with the update.

One update runs at a time; a badly signed request, or one for a commit that is not on `main`,
starts nothing.

## 1. Prepare the machine (once)

```bash
sudo apt install webhook jq curl
sudo useradd --system --create-home --home-dir /var/lib/sibylle --shell /usr/sbin/nologin --groups docker sibylle
sudo install -d -o sibylle -g sibylle /opt/sibylle
sudo -u sibylle git clone https://github.com/labnode2/sibylle.git /opt/sibylle
sudo -u sibylle -H docker login registry.labnode.ovh
```

The `docker` group is worth root: `sibylle` is only used for production. The registry does not
tell reading from writing apart: a separate account for the machine can be removed without
touching the CI's.

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
set by the Compose file; the production-only settings (tag, backups, logs) are described at the
end of `.env.example`.

For Discord to get every update, done or failed: in the chosen channel, *Edit Channel →
Integrations → Webhooks → New Webhook*, copy its URL and put it in `.env` as
`DISCORD_WEBHOOK_URL`. The URL is enough to write to the channel: it stays in `.env`, like a
secret. A machine already up to date and healthy posts nothing; a failed post is logged without
stopping the update.

## 3. First start

```bash
sudo -u sibylle -H /opt/sibylle/deploy/update.sh
sudo -u sibylle -H docker compose --project-directory /opt/sibylle/deploy -f /opt/sibylle/deploy/compose.prod.yml ps
```

`api` and `worker` must be `healthy`. The API cannot be reached from the Internet yet: that
needs nginx (see “Still missing”).

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

webhook listens on `172.17.0.1:9000`, the Docker bridge address (`ip -4 addr show docker0`):
nginx will reach it from its container, the Internet never directly. A trial on the machine,
signed the way the CI does it, with the id `trial-1`:

```bash
secret=$(sudo sed -n 's/^SIBYLLE_WEBHOOK_SECRET=//p' /etc/sibylle/webhook.env)
hook() {
  signature=$(printf '%s' "$2" | openssl dgst -sha256 -hmac "$secret" | awk '{print $NF}')
  curl -sS -H "Content-Type: application/json" -H "X-Hub-Signature-256: sha256=$signature" \
    --data-binary "$2" "http://172.17.0.1:9000/hooks/$1"
}
hook deploy "{\"id\":\"trial-1\",\"commit\":\"$(git -C /opt/sibylle rev-parse origin/main)\"}"
hook deploy-status '{"id":"trial-1"}'
```

`deploy` answers “Update started.” (202); `deploy-status` answers `state=running`, then
`state=success` or `state=failure`, followed by the log of `update.sh` (“Already up to date…”),
or `state=unknown` for an unknown id. webhook's answers: 403 without a signature or for a
malformed commit or id, 500 with “Error occurred while evaluating hook rules” for a wrong
signature. Service log: `journalctl -u sibylle-webhook`.

## 5. GitHub

In the repository's *Settings → Secrets and variables → Actions*:

- `REGISTRY_USERNAME` and `REGISTRY_PASSWORD`: the CI's account on the registry;
- `DEPLOY_WEBHOOK_SECRET`: the value from `/etc/sibylle/webhook.env`. To set once nginx relays
  `/hooks/`; until then, the “Deploy” job warns and stops there. It can live in the `production`
  environment (*Settings → Environments*), which also keeps the deployment history and can
  require an approval.

The `DEPLOY_HOOKS_URL` variable replaces `https://sibylle.cc/hooks` when needed, under which the
CI calls `deploy` and `deploy-status`.

## 6. Backups and restore

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
the machine (`age-keygen`, the private key stays offline), authorize the SSH key of `sibylle`
(`sudo -u sibylle -H ssh-keygen -t ed25519`) on the VPS, then set in `.env`
`BACKUP_AGE_RECIPIENT` (the public key) and `BACKUP_REMOTE` (the rsync destination). The VPS
keeps its copies as long as decided on its side.

## Day to day

- Deploy the latest `main` by hand: `sudo -u sibylle -H /opt/sibylle/deploy/update.sh`.
- Apply a change to `.env` without pulling an image: `update.sh --no-pull`.
- Go back to a given version: `SIBYLLE_TAG=sha-<commit>` in `.env`, then `update.sh`; remove the
  line to follow `main` again. The image from before the last update also stays on the machine,
  tagged `previous`.
- If a migration ran before a failure, `update.sh` gives the `restore.sh` command that brings
  back the database from before the update.
- Read again an update started by the CI: `/opt/sibylle/deploy-logs/<run>-<attempt>.log`, from
  the GitHub run id and the attempt number.

## Still missing

- The interface image (T207): `deploy/nginx/Dockerfile` will build `frontend/dist` with Node and
  serve it with nginx; until then, only `sibylle/backend` is in the registry, and the
  “Interface” workflow keeps the built interface as a GitHub artifact.
- nginx and certbot (T142, T210): the TLS of `sibylle.cc` and the relay of the hooks,
  `location /hooks/` to `http://host.docker.internal:9000` (with
  `extra_hosts: host.docker.internal:host-gateway`, POST only; both hooks answer at once, the
  default timeout is enough);
- frpc to the VPS's frps (T143), the DNS of `sibylle.cc` to the VPS, Brevo's SPF, DKIM and
  DMARC records (T145).
