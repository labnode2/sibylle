#!/bin/sh
# Run by the image's entrypoint before nginx starts. The certificate nginx serves: Cloudflare's
# origin certificate, mounted from the machine into /etc/nginx/tls (origin.pem and origin.key),
# else a provisional self-signed one, so that nginx starts anyway (Cloudflare refuses it in Full
# (strict) mode until the real one is in place). With SIBYLLE_ORIGIN_PULL=on, nginx also requires
# Cloudflare's client certificate (Authenticated Origin Pulls).
set -eu

dir=/run/sibylle
mkdir -p "$dir/tls"
if [ -r /etc/nginx/tls/origin.pem ] && [ -r /etc/nginx/tls/origin.key ]; then
    ln -sf /etc/nginx/tls/origin.pem "$dir/tls/cert.pem"
    ln -sf /etc/nginx/tls/origin.key "$dir/tls/key.pem"
else
    echo "$0: no origin certificate in /etc/nginx/tls, using a provisional self-signed one" >&2
    openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days 30 \
        -subj "/CN=$SIBYLLE_DOMAIN" -keyout "$dir/tls/key.pem" -out "$dir/tls/cert.pem" 2>/dev/null
fi

case ${SIBYLLE_ORIGIN_PULL:-off} in
    on)
        printf '%s\n' 'ssl_client_certificate /etc/nginx/sibylle/origin-pull-ca.pem;' \
            'ssl_verify_client on;' >"$dir/origin-pull.conf"
        ;;
    off)
        : >"$dir/origin-pull.conf"
        ;;
    *)
        echo "$0: SIBYLLE_ORIGIN_PULL must be on or off" >&2
        exit 1
        ;;
esac
