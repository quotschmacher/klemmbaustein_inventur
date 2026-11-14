FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client curl ca-certificates git ripgrep jq xz-utils libatomic1 build-essential \
    && rm -rf /var/lib/apt/lists/*
# Node.js 22 is installed by the Dev Containers feature in devcontainer.json.
# Hermes should run in this workspace after user setup; do not bake model API credentials into images.
