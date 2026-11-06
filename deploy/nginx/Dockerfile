# The web image: the interface built by Node, then served by nginx with the production
# configuration of deploy/nginx/ (templates/sibylle.conf.template). Built from the repository
# root, which Dockerfile.dockerignore narrows down to frontend/ and deploy/nginx/:
#   docker build -f deploy/nginx/Dockerfile --build-arg SIBYLLE_COMMIT=$(git rev-parse HEAD) \
#     -t sibylle-web .

# The Node of frontend/.nvmrc, on Debian like the CI's runners.
FROM node:26.13.0-slim AS build
WORKDIR /src
# The dependencies first, in their own layer: it only changes with package-lock.json.
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY frontend/ ./
# The commit shown with the interface's version (frontend/vite.config.ts): there is no .git here
# to read it from. Declared after `npm ci`, so that a new commit keeps that layer cached.
ARG SIBYLLE_COMMIT=
RUN npm run build

FROM nginx:1.30-alpine
# nginx's own site and pages go, and its `user` directive: it already runs as that user
# (compose.prod.yml), and the directive would only warn.
RUN rm /etc/nginx/conf.d/default.conf \
    && rm -r /usr/share/nginx/html/* \
    && sed -i '/^user /d' /etc/nginx/nginx.conf
# Only the SIBYLLE_* variables are filled into the templates: nginx's own ($host…) stay as they
# are.
ENV NGINX_ENVSUBST_FILTER=^SIBYLLE_
COPY deploy/nginx/templates/ /etc/nginx/templates/
COPY deploy/nginx/entrypoint/ /docker-entrypoint.d/
COPY --from=build /src/dist/ /usr/share/nginx/html/
# Plain HTTP: NPM terminates TLS in front of it (compose.prod.yml).
EXPOSE 8443
