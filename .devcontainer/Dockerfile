# syntax=docker/dockerfile:1.7

# ============================================================
# Single entry point: install.sh handles mise + chezmoi + tools
# ============================================================
ARG BASE_IMAGE=ubuntu:25.10

FROM ${BASE_IMAGE} AS base

ARG DEBIAN_FRONTEND=noninteractive
ARG APT_SNAPSHOT=20260328T000000Z

ENV DEBIAN_FRONTEND=${DEBIAN_FRONTEND}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# APT snapshot pinning for reproducible builds
RUN --mount=type=cache,id=apt-cache-${APT_SNAPSHOT},target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=apt-lists-${APT_SNAPSHOT},target=/var/lib/apt/lists,sharing=locked \
    distro="$(. /etc/os-release && printf '%s' "$ID")" && \
    codename="$(. /etc/os-release && printf '%s' "$VERSION_CODENAME")" && \
    case "$distro" in \
      ubuntu) \
        apt-get update && \
        apt-get install -y --no-install-recommends ca-certificates ubuntu-keyring && \
        find /etc/apt/sources.list.d -name '*.sources' -exec \
          sed -i -E "s|URIs: https?://[^ ]+/ubuntu/?|URIs: https://snapshot.ubuntu.com/ubuntu/${APT_SNAPSHOT}/|g" {} + && \
        printf 'Acquire::Check-Valid-Until "false";\n' >/etc/apt/apt.conf.d/90snapshot \
        ;; \
      debian) \
        printf '%s\n' \
          'Types: deb' \
          "URIs: http://snapshot.debian.org/archive/debian/${APT_SNAPSHOT}/" \
          "Suites: ${codename} ${codename}-updates" \
          'Components: main' \
          'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
          '' \
          'Types: deb' \
          "URIs: http://snapshot.debian.org/archive/debian-security/${APT_SNAPSHOT}/" \
          "Suites: ${codename}-security" \
          'Components: main' \
          'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
          >/etc/apt/sources.list.d/debian.sources && \
        printf 'Acquire::Check-Valid-Until "false";\n' >/etc/apt/apt.conf.d/90snapshot \
        ;; \
    esac

# Bare minimum system dependencies (everything else via mise)
RUN --mount=type=cache,id=apt-cache-${APT_SNAPSHOT},target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=apt-lists-${APT_SNAPSHOT},target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    sudo \
    zsh \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libatomic1 \
    && rm -rf /tmp/*

# ---------- dotfiles bootstrap ----------
FROM base AS tools

# Run bootstrap as root (tools install to neutral system paths)
COPY . /tmp/dotfiles
RUN --mount=type=cache,target=/root/.cache/mise,uid=0,gid=0 \
    --mount=type=cache,target=/root/.cache/uv,uid=0,gid=0 \
    --mount=type=cache,target=/root/.cache/chezmoi,uid=0,gid=0 \
    --mount=type=cache,target=/root/.pkl,uid=0,gid=0 \
    --mount=type=secret,id=github_token \
    if [ -f /run/secrets/github_token ]; then \
      export GITHUB_TOKEN="$(cat /run/secrets/github_token)"; \
      export MISE_GITHUB_TOKEN="$GITHUB_TOKEN"; \
    fi && \
    cd /tmp/dotfiles && bash install.sh --local

# ---------- devcontainer (default user + SSH) ----------
FROM tools AS devcontainer

ARG DEVCONTAINER_USERNAME=devcontainer
ARG USER_UID=1000
ARG USER_GID=1000

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    && rm -rf /var/lib/apt/lists/* /tmp/*

RUN groupadd --gid ${USER_GID} ${DEVCONTAINER_USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} -m -s /bin/bash ${DEVCONTAINER_USERNAME} \
    && echo "${DEVCONTAINER_USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${DEVCONTAINER_USERNAME} \
    && chmod 0440 /etc/sudoers.d/${DEVCONTAINER_USERNAME} \
    && mkdir -p /home/${DEVCONTAINER_USERNAME}/.ssh \
    && chmod 700 /home/${DEVCONTAINER_USERNAME}/.ssh \
    && chown ${DEVCONTAINER_USERNAME}:${DEVCONTAINER_USERNAME} /home/${DEVCONTAINER_USERNAME}/.ssh

# Pre-stage cache directories
RUN mkdir -p \
    /home/${DEVCONTAINER_USERNAME}/.cache/uv \
    /home/${DEVCONTAINER_USERNAME}/.local/share/mise \
    /home/${DEVCONTAINER_USERNAME}/.local/bin \
    /home/${DEVCONTAINER_USERNAME}/.local/state \
    /home/${DEVCONTAINER_USERNAME}/.claude \
    /home/${DEVCONTAINER_USERNAME}/.codex \
    /home/${DEVCONTAINER_USERNAME}/.gemini \
    /home/${DEVCONTAINER_USERNAME}/.config/gh \
    && chown -R ${DEVCONTAINER_USERNAME}:${DEVCONTAINER_USERNAME} /home/${DEVCONTAINER_USERNAME}

ENV USER=${DEVCONTAINER_USERNAME} \
    HOME=/home/${DEVCONTAINER_USERNAME} \
    PATH="/home/${DEVCONTAINER_USERNAME}/.local/bin:/home/${DEVCONTAINER_USERNAME}/.local/share/mise/shims:${PATH}"

USER ${DEVCONTAINER_USERNAME}
WORKDIR /home/${DEVCONTAINER_USERNAME}
