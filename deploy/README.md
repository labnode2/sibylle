# Mise en production

La production tourne sur la machine à domicile, qui est aussi le PC de développement. Elle vit à
part : un clone du dépôt dans `/opt/sibylle`, un projet Compose `sibylle-prod`
(`deploy/compose.prod.yml`) avec ses propres volumes et aucun port publié, et un utilisateur
système `sibylle`. Le développement (projet `sibylle`, base sur le port 5432) n'est jamais touché.

## Comment une mise à jour arrive

1. Un push sur `main` lance le workflow « Serveur » : ruff, mypy, pytest, puis l'image
   `registry.labnode.ovh/sibylle/backend`, taguée `main` et `sha-<commit>`.
2. Le job « Déployer » appelle `https://sibylle.cc/hooks/deploy` avec le commit, signé
   (HMAC-SHA256 du corps, avec le secret partagé).
3. nginx relaie la requête à webhook, qui tourne sur la machine (service
   `sibylle-webhook`) ; webhook vérifie la signature et lance `deploy/update.sh <commit>`.
4. `update.sh` met `/opt/sibylle` sur `main`, tire l'image, sauvegarde la base et les images
   envoyées, redémarre, puis attend que chaque service soit en bonne santé. Si l'un d'eux ne
   l'est pas, il revient à la version précédente et le dit.
5. Son journal revient à GitHub comme réponse : le job « Déployer » est vert ou rouge avec lui.

Une seule mise à jour tourne à la fois ; une requête mal signée, ou pour un commit qui n'est pas
sur `main`, ne lance rien.

## 1. Préparer la machine (une fois)

```bash
sudo apt install webhook jq
sudo useradd --system --create-home --home-dir /var/lib/sibylle --shell /usr/sbin/nologin --groups docker sibylle
sudo install -d -o sibylle -g sibylle /opt/sibylle
sudo -u sibylle git clone https://github.com/labnode2/sibylle.git /opt/sibylle
sudo -u sibylle -H docker login registry.labnode.ovh
```

Le groupe `docker` vaut les droits root : `sibylle` ne sert qu'à la production. Le registre ne
distingue pas lecture et écriture : un compte à part pour la machine se retire sans toucher à
celui de la CI.

## 2. Réglages de production

```bash
sudo -u sibylle cp /opt/sibylle/deploy/.env.example /opt/sibylle/deploy/.env
sudo -u sibylle chmod 600 /opt/sibylle/deploy/.env
sudo -u sibylle -H docker run --rm registry.labnode.ovh/sibylle/backend:main gen-secrets
sudo -u sibylle -e /opt/sibylle/deploy/.env
```

Dans `.env` : `ENVIRONMENT=production`, `PUBLIC_ORIGIN=https://sibylle.cc`, les trois secrets
affichés par `gen-secrets` (`POSTGRES_PASSWORD`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`), les
e-mails de Brevo (`SMTP_*`, `MAIL_FROM`) et `VAPID_SUBJECT`. `DATABASE_URL` et `UPLOAD_DIR` sont
posés par le Compose ; les réglages propres à la production (tag, sauvegardes) sont décrits à la
fin de `.env.example`.

## 3. Premier démarrage

```bash
sudo -u sibylle -H /opt/sibylle/deploy/update.sh
sudo -u sibylle -H docker compose --project-directory /opt/sibylle/deploy -f /opt/sibylle/deploy/compose.prod.yml ps
```

`api` et `worker` doivent être `healthy`. L'API n'est pas encore joignable depuis Internet :
il faut nginx (voir « Ce qui manque encore »).

## 4. Le crochet de déploiement

Un secret de 64 caractères, lisible par root seul :

```bash
sudo install -d -m 700 /etc/sibylle
sudo sh -c 'umask 077; printf "SIBYLLE_WEBHOOK_SECRET=%s\n" "$(openssl rand -hex 32)" > /etc/sibylle/webhook.env'
```

Les services, copiés (et non liés) pour que les fichiers d'unité restent à root :

```bash
sudo cp /opt/sibylle/deploy/systemd/sibylle-webhook.service /opt/sibylle/deploy/systemd/sibylle-backup.service /opt/sibylle/deploy/systemd/sibylle-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sibylle-webhook.service sibylle-backup.timer
```

webhook écoute sur `172.17.0.1:9000`, l'adresse du pont Docker (`ip -4 addr show docker0`) : nginx
le joindra depuis son conteneur, Internet jamais directement. Essai sur la machine, signé comme
le fait la CI :

```bash
secret=$(sudo sed -n 's/^SIBYLLE_WEBHOOK_SECRET=//p' /etc/sibylle/webhook.env)
body="{\"commit\":\"$(git -C /opt/sibylle rev-parse origin/main)\"}"
signature=$(printf '%s' "$body" | openssl dgst -sha256 -hmac "$secret" | awk '{print $NF}')
curl -sS -H "Content-Type: application/json" -H "X-Hub-Signature-256: sha256=$signature" \
  --data-binary "$body" http://172.17.0.1:9000/hooks/deploy
```

La réponse est le journal de `update.sh` (« Déjà à jour… »). Réponses de webhook : 403 sans
signature ou pour un commit mal formé, 500 avec « Error occurred while evaluating hook rules »
pour une mauvaise signature, 500 avec le journal si la mise à jour échoue. Journal du service :
`journalctl -u sibylle-webhook`.

## 5. GitHub

Dans *Settings → Secrets and variables → Actions* du dépôt :

- `REGISTRY_USERNAME` et `REGISTRY_PASSWORD` : le compte de la CI sur le registre ;
- `DEPLOY_WEBHOOK_SECRET` : la valeur de `/etc/sibylle/webhook.env`. À poser une fois que nginx
  relaie `/hooks/deploy` ; d'ici là, le job « Déployer » prévient et s'arrête là. On peut le ranger
  dans l'environnement `production` (*Settings → Environments*), qui garde aussi l'historique des
  déploiements et peut exiger une approbation.

La variable `DEPLOY_WEBHOOK_URL` remplace au besoin `https://sibylle.cc/hooks/deploy`.

## 6. Sauvegardes et restauration

`deploy/backup/backup.sh` sauvegarde la base (`pg_dump` au format personnalisé) et les images
envoyées dans `/opt/sibylle/backups`, chaque nuit vers 3 h 30 (`sibylle-backup.timer`) et avant
chaque mise à jour ; 14 jours sont gardés. `sudo systemctl start sibylle-backup` en fait une tout
de suite.

Restaurer une sauvegarde (l'API et le worker s'arrêtent le temps de la restauration) :

```bash
sudo -u sibylle -H /opt/sibylle/deploy/backup/restore.sh --yes \
  /opt/sibylle/backups/sibylle-AAAAMMJJ-HHMMSS-nightly.dump \
  /opt/sibylle/backups/sibylle-AAAAMMJJ-HHMMSS-nightly.uploads.tar.gz
```

Copie chiffrée sur le VPS, chaque nuit : installer `age`, créer la paire de clés ailleurs que sur
la machine (`age-keygen`, la clé privée reste hors ligne), autoriser la clé SSH de `sibylle`
(`sudo -u sibylle -H ssh-keygen -t ed25519`) sur le VPS, puis poser dans `.env`
`BACKUP_AGE_RECIPIENT` (la clé publique) et `BACKUP_REMOTE` (la destination rsync). Le VPS
garde ses copies aussi longtemps qu'on le décide de son côté.

## Au quotidien

- Déployer à la main la dernière version de `main` : `sudo -u sibylle -H /opt/sibylle/deploy/update.sh`.
- Appliquer un changement de `.env` sans tirer d'image : `update.sh --no-pull`.
- Revenir à une version précise : `SIBYLLE_TAG=sha-<commit>` dans `.env`, puis `update.sh` ;
  retirer la ligne pour suivre `main` de nouveau. L'image d'avant la dernière mise à jour reste
  aussi sur la machine, taguée `previous`.
- Si une migration est passée avant un échec, `update.sh` donne la commande `restore.sh` qui
  remet la base d'avant la mise à jour.

## Ce qui manque encore

- nginx et certbot (T142, T207, T210) : l'interface, le TLS de `sibylle.cc` et le relais du
  crochet, `location = /hooks/deploy` vers `http://host.docker.internal:9000` (avec
  `extra_hosts: host.docker.internal:host-gateway`, POST seulement, `proxy_read_timeout` de
  900 s) ;
- frpc vers le frps du VPS (T143), le DNS de `sibylle.cc` vers le VPS, les enregistrements SPF,
  DKIM et DMARC de Brevo (T145).
