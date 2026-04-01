# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=ubuntu:25.10
ARG MISE_VERSION=v2026.3.18

FROM ${BASE_IMAGE} AS devcontainer

ARG DEBIAN_FRONTEND=noninteractive
ARG MISE_VERSION

ENV DEBIAN_FRONTEND=${DEBIAN_FRONTEND} \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    MISE_INSTALL_PATH=/usr/local/bin/mise \
    MISE_TRUSTED_CONFIG_PATHS=/root/.config/mise \
    CONDA_SUBDIR=linux-64 \
    MISE_HTTP_TIMEOUT=120 \
    npm_config_update_notifier=false

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    sed -i '/path-exclude=\\/usr\\/share\\/man\\/*/d' /etc/dpkg/dpkg.cfg.d/excludes && \
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

COPY .chezmoiroot /tmp/dotfiles/.chezmoiroot
COPY .chezmoiversion /tmp/dotfiles/.chezmoiversion
COPY docs /tmp/dotfiles/docs
COPY home /tmp/dotfiles/home
COPY install.sh /tmp/dotfiles/install.sh

RUN --mount=type=cache,id=mise-cache,target=/root/.cache/mise,sharing=locked \
    --mount=type=cache,id=uv-cache,target=/root/.cache/uv,sharing=locked \
    --mount=type=secret,id=github_token \
    export MISE_VERSION="${MISE_VERSION}" && \
    export MISE_INSTALL_MODE=system && \
    export UV_LINK_MODE=copy && \
    if [ -f /run/secrets/github_token ]; then \
      export GITHUB_TOKEN="$(cat /run/secrets/github_token)"; \
      export MISE_GITHUB_TOKEN="$GITHUB_TOKEN"; \
    fi && \
    cd /tmp/dotfiles && ./install.sh

WORKDIR /workspaces
