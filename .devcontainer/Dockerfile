# syntax=docker/dockerfile:1.7
# check=error=true

ARG BASE_IMAGE=ubuntu:25.10
ARG MISE_VERSION=v2026.4.4

FROM ${BASE_IMAGE} AS devcontainer

ARG DEBIAN_FRONTEND=noninteractive
ARG MISE_VERSION

# Only PATH and mise directory layout stay as Docker ENV.
# All other vars (locale, platform hints, tool config) live in
# .devcontainer/mise-system.toml [env] so mise owns them.
ENV MISE_DATA_DIR=/opt/mise \
    MISE_CONFIG_DIR=/etc/mise \
    MISE_INSTALL_PATH=/usr/local/bin/mise \
    MISE_TRUSTED_CONFIG_PATHS=/etc/mise:/workspaces/dotfiles \
    CARGO_HOME=/opt/cargo \
    RUSTUP_HOME=/opt/rustup \
    PATH="/usr/local/bin:/opt/mise/shims:/opt/cargo/bin:${PATH}"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    export DEBIAN_FRONTEND=noninteractive && \
    sed -i '/^path-exclude=\/usr\/share\/man\/\*$/d' /etc/dpkg/dpkg.cfg.d/excludes && \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    gnupg \
    graphviz \
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

# Install mise globally
RUN curl -fsSL https://mise.jdx.dev/mise-latest-linux-x64 > /usr/local/bin/mise && \
    chmod +x /usr/local/bin/mise

# System-wide mise config and data structure
RUN groupadd --gid 2000 mise && \
    mkdir -p /etc/mise /opt/mise /opt/cargo /opt/rustup && \
    chown -R :mise /opt/mise /opt/cargo /opt/rustup && \
    chmod -R 775 /opt/mise /opt/cargo /opt/rustup

# Copy dedicated system config — no chezmoi dependency, no sed stripping
COPY .devcontainer/mise-system.toml /etc/mise/config.toml

# Pre-install tools globally via mise
RUN --mount=type=cache,id=mise-cache,target=/opt/mise/cache,sharing=locked \
    --mount=type=cache,id=uv-cache,target=/root/.cache/uv,sharing=locked \
    --mount=type=secret,id=github_token \
    export MISE_VERSION="${MISE_VERSION}" && \
    export MISE_INSTALL_MODE=system && \
    export UV_LINK_MODE=copy && \
    export LANG=C.UTF-8 && \
    export LC_ALL=C.UTF-8 && \
    if [ -f /run/secrets/github_token ]; then \
      GITHUB_TOKEN="$(cat /run/secrets/github_token)" && \
      export GITHUB_TOKEN && \
      export MISE_GITHUB_TOKEN="$GITHUB_TOKEN"; \
    fi && \
    mise install -y && \
    chmod -R 777 /opt/mise /etc/mise /opt/cargo /opt/rustup

# Reshim to ensure all shims are present (aqua tools may include doc-file
# shims like LICENSE, README — these are harmless and must not be deleted
# or mise doctor will report them as missing)
RUN mise reshim -f

# Final global permissions check
RUN chmod -R 777 /opt/mise /etc/mise /opt/cargo /opt/rustup

# Ensure mise is activated for all users
RUN echo "eval \"\$(/usr/local/bin/mise activate bash)\"" > /etc/profile.d/mise.sh && \
    echo "eval \"\$(/usr/local/bin/mise activate zsh)\"" > /etc/profile.d/mise.zsh

WORKDIR /workspaces
