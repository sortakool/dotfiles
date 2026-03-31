# syntax=docker/dockerfile:1.7

# ============================================================
# Single entry point: install.sh handles mise + chezmoi + tools
# ============================================================
ARG BASE_IMAGE=ubuntu:25.10

FROM ${BASE_IMAGE} AS base

ARG DEBIAN_FRONTEND=noninteractive

ENV DEBIAN_FRONTEND=${DEBIAN_FRONTEND}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# System dependencies (everything else via mise)
# Uses default archive.ubuntu.com mirrors — no snapshot pinning.
# Zero out of 456 GitHub projects using ubuntu:25.10 use snapshot pinning;
# snapshot.ubuntu.com has known reliability issues (503s, rate limiting).
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    gnupg \
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

ARG DEVCONTAINER_USERNAME=devcontainer

ENV MISE_DATA_DIR=/opt/mise \
    MISE_CACHE_DIR=/opt/mise/cache \
    MISE_ALWAYS_KEEP_DOWNLOAD=1 \
    HOME=/home/${DEVCONTAINER_USERNAME} \
    RUSTUP_HOME=/home/${DEVCONTAINER_USERNAME}/.rustup \
    CARGO_HOME=/home/${DEVCONTAINER_USERNAME}/.cargo \
    RUSTUP_INIT_SKIP_PATH_CHECK=yes \
    npm_config_update_notifier=false

# Pre-create home so install.sh writes to the final user's home, not /root.
# Avoids all /root permission and path issues when running as non-root user.
RUN mkdir -p /home/${DEVCONTAINER_USERNAME}

COPY . /tmp/dotfiles
RUN --mount=type=cache,id=mise-cache,target=/opt/mise/cache,sharing=locked \
    --mount=type=cache,id=uv-cache,target=${HOME}/.cache/uv,sharing=locked \
    --mount=type=cache,id=chezmoi-cache,target=${HOME}/.cache/chezmoi,sharing=locked \
    --mount=type=cache,id=pkl-cache,target=${HOME}/.pkl,sharing=locked \
    --mount=type=cache,id=npm-cache,target=${HOME}/.npm,sharing=locked \
    --mount=type=secret,id=github_token \
    export UV_LINK_MODE=copy && \
    if [ -f /run/secrets/github_token ]; then \
      export GITHUB_TOKEN="$(cat /run/secrets/github_token)"; \
      export MISE_GITHUB_TOKEN="$GITHUB_TOKEN"; \
    fi && \
    cd /tmp/dotfiles && bash install.sh --local

# ---------- devcontainer (default user + SSH) ----------
FROM tools AS devcontainer

ARG USER_UID=1000
ARG USER_GID=1000

# Create or rename existing UID/GID 1000 user/group to DEVCONTAINER_USERNAME.
# ubuntu:25.10 ships with an 'ubuntu' user at UID/GID 1000 — handle gracefully.
RUN existing_group="$(getent group ${USER_GID} | cut -d: -f1 || true)" && \
    if [ -n "${existing_group}" ] && [ "${existing_group}" != "${DEVCONTAINER_USERNAME}" ]; then \
      groupmod -n "${DEVCONTAINER_USERNAME}" "${existing_group}"; \
    elif [ -z "${existing_group}" ]; then \
      groupadd --gid ${USER_GID} ${DEVCONTAINER_USERNAME}; \
    fi && \
    existing_user="$(getent passwd ${USER_UID} | cut -d: -f1 || true)" && \
    if [ -n "${existing_user}" ] && [ "${existing_user}" != "${DEVCONTAINER_USERNAME}" ]; then \
      usermod --login "${DEVCONTAINER_USERNAME}" \
              --home "/home/${DEVCONTAINER_USERNAME}" "${existing_user}"; \
      rm -rf "/home/${existing_user}"; \
    elif [ -z "${existing_user}" ]; then \
      useradd --uid ${USER_UID} --gid ${USER_GID} --no-create-home -s /bin/bash ${DEVCONTAINER_USERNAME}; \
    fi && \
    usermod --shell /bin/bash "${DEVCONTAINER_USERNAME}" && \
    echo "${DEVCONTAINER_USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${DEVCONTAINER_USERNAME} && \
    chmod 0440 /etc/sudoers.d/${DEVCONTAINER_USERNAME} && \
    mkdir -p /home/${DEVCONTAINER_USERNAME}/.ssh && \
    chmod 700 /home/${DEVCONTAINER_USERNAME}/.ssh && \
    chown ${DEVCONTAINER_USERNAME}:${DEVCONTAINER_USERNAME} /home/${DEVCONTAINER_USERNAME}/.ssh

# Pre-stage cache directories and fix /opt/mise ownership.
# /opt/mise was created by root in the tools stage; the devcontainer user needs
# write access for mise cache operations at runtime.
RUN mkdir -p \
    /home/${DEVCONTAINER_USERNAME}/.cache/uv \
    /home/${DEVCONTAINER_USERNAME}/.local/bin \
    /home/${DEVCONTAINER_USERNAME}/.local/state \
    /home/${DEVCONTAINER_USERNAME}/.claude \
    /home/${DEVCONTAINER_USERNAME}/.codex \
    /home/${DEVCONTAINER_USERNAME}/.gemini \
    /home/${DEVCONTAINER_USERNAME}/.config/gh \
    && chown -R ${DEVCONTAINER_USERNAME}:${DEVCONTAINER_USERNAME} /home/${DEVCONTAINER_USERNAME} \
    && chown -R ${DEVCONTAINER_USERNAME}:${DEVCONTAINER_USERNAME} /opt/mise

ENV USER=${DEVCONTAINER_USERNAME} \
    HOME=/home/${DEVCONTAINER_USERNAME} \
    MISE_DATA_DIR=/opt/mise \
    RUSTUP_HOME=/home/${DEVCONTAINER_USERNAME}/.rustup \
    CARGO_HOME=/home/${DEVCONTAINER_USERNAME}/.cargo \
    PATH="/home/${DEVCONTAINER_USERNAME}/.cargo/bin:/home/${DEVCONTAINER_USERNAME}/.local/bin:/opt/mise/shims:${PATH}"

USER ${DEVCONTAINER_USERNAME}
WORKDIR /home/${DEVCONTAINER_USERNAME}
