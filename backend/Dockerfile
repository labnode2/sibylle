# L'image du serveur : l'API (`sibylle serve`, la commande par défaut, qui applique d'abord les
# migrations) et le worker (`sibylle worker`) en sortent tous deux. Construite depuis backend/ :
#   docker build -t sibylle-backend backend
# Elle tourne sous un utilisateur sans droits ; seules les images envoyées s'écrivent, dans
# /data/uploads.

FROM python:3.14-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /bin/uv
# Le bytecode compilé une fois pour toutes, des copies plutôt que des liens vers le cache (un
# montage qui disparaît après la construction), le Python de l'image et pas un autre, et
# l'environnement dans /app, qui passe tel quel dans l'image finale.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0 UV_PROJECT_ENVIRONMENT=/app
WORKDIR /src
# Les dépendances d'abord, dans leur propre couche : elle ne change qu'avec uv.lock.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

FROM python:3.14-slim
RUN useradd --system --user-group --uid 10001 --no-create-home --home-dir /nonexistent \
        --shell /usr/sbin/nologin sibylle \
    && mkdir -p /data/uploads \
    && chown -R sibylle:sibylle /data
COPY --from=build /app /app
ENV PATH=/app/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    UPLOAD_DIR=/data/uploads
WORKDIR /data
USER sibylle
EXPOSE 8000
ENTRYPOINT ["sibylle"]
CMD ["serve"]
