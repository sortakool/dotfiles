# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=ubuntu:25.10
ARG MISE_VERSION=v2026.3.18

FROM ${BASE_IMAGE} AS devcontainer

ARG DEBIAN_FRONTEND=noninteractive
ARG MISE_VERSION

ENV DEBIAN_FRONTEND=${DEBIAN_FRONTEND} \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    MISE_DATA_DIR=/opt/mise \
    MISE_CACHE_DIR=/opt/mise/cache \
    MISE_ALWAYS_KEEP_DOWNLOAD=1 \
    CONDA_SUBDIR=linux-64 \
    CARGO_HOME=/opt/data/cargo \
    RUSTUP_HOME=/opt/data/rustup \
    NPM_CONFIG_PREFIX=/opt/data/npm \
    NPM_CONFIG_CACHE=/opt/data/npm/cache \
    GOPATH=/opt/data/go \
    GOBIN=/opt/data/go/bin \
    GOMODCACHE=/opt/data/go/mod \
    GOCACHE=/opt/data/go/cache \
    MISE_HTTP_TIMEOUT=120 \
    RUSTUP_INIT_SKIP_PATH_CHECK=yes \
    npm_config_update_notifier=false \
    PATH=/opt/data/cargo/bin:/opt/data/go/bin:/opt/data/npm/bin:/root/.local/bin:/opt/mise/shims:${PATH}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    gnupg \
    pkg-config \
    unzip \
    zsh \
    libatomic1 \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libssl-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/* /tmp/*

RUN mkdir -p \
    /opt/mise/cache \
    /opt/data/uv/cache \
    /opt/data/npm/cache \
    /opt/data/pkl

COPY .chezmoiroot /tmp/dotfiles/.chezmoiroot
COPY .chezmoiversion /tmp/dotfiles/.chezmoiversion
COPY docs /tmp/dotfiles/docs
COPY home /tmp/dotfiles/home
COPY install.sh /tmp/dotfiles/install.sh

RUN --mount=type=cache,id=mise-cache,target=/opt/mise/cache,sharing=locked \
    --mount=type=cache,id=uv-cache,target=/opt/data/uv/cache,sharing=locked \
    --mount=type=cache,id=npm-cache,target=/opt/data/npm/cache,sharing=locked \
    --mount=type=cache,id=pkl-cache,target=/opt/data/pkl,sharing=locked \
    --mount=type=secret,id=github_token \
    export MISE_VERSION="${MISE_VERSION}" && \
    export UV_LINK_MODE=copy && \
    if [ -f /run/secrets/github_token ]; then \
      export GITHUB_TOKEN="$(cat /run/secrets/github_token)"; \
      export MISE_GITHUB_TOKEN="$GITHUB_TOKEN"; \
    fi && \
    cd /tmp/dotfiles && ./install.sh

WORKDIR /workspaces
