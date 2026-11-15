FROM node:22-bookworm-slim AS node

FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm
COPY --from=node /usr/local /usr/local
# The base image may retain an obsolete Yarn APT source whose signature is no
# longer trusted. Node is copied from the explicit Node 22 build stage.
RUN rm -f /etc/apt/sources.list.d/yarn.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client curl ca-certificates git ripgrep jq xz-utils libatomic1 build-essential \
    && rm -rf /var/lib/apt/lists/*
# Python/Node dependencies are installed after the workspace is mounted by
# devcontainer.json. This image is also usable directly through Compose.
# Hermes should run in this workspace after user setup; do not bake model API credentials into images.
