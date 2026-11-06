# The web image: the interface built by Node, then served by nginx with the production
# configuration of deploy/nginx/ (templates/sibylle.conf.template). Built from the repository
# root, which Dockerfile.dockerignore narrows down to frontend/ and deploy/nginx/:
#   docker build -f deploy/nginx/Dockerfile -t sibylle-web .

# The Node of frontend/.nvmrc, on Debian like the CI's runners.
FROM node:26.13.0-slim AS build
WORKDIR /src
# The dependencies first, in their own layer: it only changes with package-lock.json.
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM nginx:1.30-alpine
# openssl makes the provisional certificate (entrypoint/40-sibylle-tls.sh); nginx's own site and
# pages go.
RUN apk add --no-cache openssl \
    && rm /etc/nginx/conf.d/default.conf \
    && rm -r /usr/share/nginx/html/*
# Only the SIBYLLE_* variables are filled into the templates: nginx's own ($host…) stay as they
# are.
ENV NGINX_ENVSUBST_FILTER=^SIBYLLE_
COPY deploy/nginx/templates/ /etc/nginx/templates/
COPY deploy/nginx/cloudflare/ /etc/nginx/sibylle/
COPY deploy/nginx/entrypoint/ /docker-entrypoint.d/
COPY --from=build /src/dist/ /usr/share/nginx/html/
EXPOSE 443
