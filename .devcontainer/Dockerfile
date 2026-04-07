# syntax=docker/dockerfile:1.7
# check=error=true

ARG BASE_IMAGE=ubuntu:25.10
ARG MISE_VERSION=v2026.4.5

FROM ${BASE_IMAGE} AS devcontainer

ARG DEBIAN_FRONTEND=noninteractive
ARG MISE_VERSION

# Only PATH and mise directory layout stay as Docker ENV.
# All other vars (locale, platform hints, tool config) live in
# .devcontainer/mise-system.toml [env] so mise owns them.
#
# Cookbook canonical layout per https://mise.jdx.dev/mise-cookbook/docker:
#   - MISE_DATA_DIR pins installs/shims to /usr/local/share/mise. Without
#     it, build-time `mise install` (as root) writes to XDG default
#     /root/.local/share/mise — invisible to PATH and to non-root users.
#   - MISE_CONFIG_DIR tells mise WHERE to discover the system config
#     (mise reads $MISE_CONFIG_DIR/config.toml). Without it, mise has
#     no idea our COPY destination /usr/local/share/mise/config.toml is
#     a config — `mise install -y` silently no-ops because it discovers
#     zero configs. (MISE_TRUSTED_CONFIG_PATHS only AUTHORIZES a path,
#     it does not DISCOVER configs there. Trust + discovery are
#     orthogonal — both are required.)
#   - The cookbook explicitly sets BOTH vars to the same path (`/mise`)
#     and so must we.
#   - PR-2 will layer per-user overlays via named volumes at
#     ~/.local/share/mise (devcontainer feature mount), so the system
#     path remains the canonical baked location while users get mutable
#     overlays at runtime.
ENV MISE_DATA_DIR=/usr/local/share/mise \
    MISE_CONFIG_DIR=/usr/local/share/mise \
    MISE_INSTALL_PATH=/usr/local/bin/mise \
    MISE_TRUSTED_CONFIG_PATHS=/usr/local/share/mise:/workspaces/dotfiles \
    CARGO_HOME=/opt/cargo \
    RUSTUP_HOME=/opt/rustup \
    PATH="/usr/local/bin:/usr/local/share/mise/shims:/opt/cargo/bin:${PATH}"

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
    sudo \
    unzip \
    zsh \
    libatomic1 \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libssl-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/* /tmp/*

# Install mise globally (pinned version to prevent stale CDN cache issues)
RUN curl -fsSL "https://mise.jdx.dev/${MISE_VERSION}/mise-${MISE_VERSION}-linux-x64" > /usr/local/bin/mise && \
    chmod +x /usr/local/bin/mise

# System-wide mise config and data structure (cookbook canonical paths).
RUN groupadd --gid 2000 mise && \
    mkdir -p /usr/local/share/mise /opt/cargo /opt/rustup && \
    chown -R :mise /usr/local/share/mise /opt/cargo /opt/rustup && \
    chmod -R 775 /usr/local/share/mise /opt/cargo /opt/rustup

# Copy dedicated system config — no chezmoi dependency, no sed stripping
COPY .devcontainer/mise-system.toml /usr/local/share/mise/config.toml

# Pre-install tools globally via mise
# Known cosmetic warnings during install:
# - rustup "existing settings file": rustup-init creates settings.toml then
#   check_existence_of_settings_file() warns about its own file. Fixed via
#   RUSTUP_INIT_SKIP_EXISTENCE_CHECKS=yes (undocumented env var, see
#   rust-lang/rustup/src/cli/self_update.rs). RUSTUP_INIT_SKIP_PATH_CHECK
#   in mise-system.toml [env] is a different check (PATH validation).
# - bun "add the global bin folder to $PATH": bun checks if its bin output
#   directory exists on $PATH at install time. During Docker RUN, PATH only
#   includes /usr/local/share/mise/shims — not bun's per-package bin dirs. At runtime,
#   mise shims intercept all lookups so the warning is cosmetic. No bun env
#   var (BUN_QUIET, BUN_LOG_LEVEL) suppresses this — it's hardcoded in bun's
#   install reporter. Unfixable: fundamental mismatch between bun's PATH-based
#   assumptions and mise's shim resolution model.
RUN --mount=type=cache,id=mise-cache,target=/usr/local/share/mise/cache,sharing=locked \
    --mount=type=cache,id=uv-cache,target=/root/.cache/uv,sharing=locked \
    --mount=type=secret,id=github_token \
    export MISE_VERSION="${MISE_VERSION}" && \
    export MISE_INSTALL_MODE=system && \
    export UV_LINK_MODE=copy && \
    export LANG=C.UTF-8 && \
    export LC_ALL=C.UTF-8 && \
    export RUSTUP_INIT_SKIP_EXISTENCE_CHECKS=yes && \
    if [ -f /run/secrets/github_token ]; then \
      GITHUB_TOKEN="$(cat /run/secrets/github_token)" && \
      export GITHUB_TOKEN && \
      export MISE_GITHUB_TOKEN="$GITHUB_TOKEN"; \
    fi && \
    mise install -y && \
    chmod -R 777 /usr/local/share/mise /opt/cargo /opt/rustup

# Reshim to ensure all shims are present (aqua tools may include doc-file
# shims like LICENSE, README — these are harmless and must not be deleted
# or mise doctor will report them as missing)
RUN mise reshim -f

# Final global permissions check
RUN chmod -R 777 /usr/local/share/mise /opt/cargo /opt/rustup

# Copy image-specific hk config + shared checks for smoke-test validation.
# hk-image.pkl imports hk-common.pkl — both must be in /etc/hk/ for pkl
# relative import resolution. hk-image.pkl is renamed to hk.pkl (hk default).
COPY hk-common.pkl /etc/hk/hk-common.pkl
COPY hk-image.pkl /etc/hk/hk.pkl

# Ensure mise is activated for all users
RUN echo "eval \"\$(/usr/local/bin/mise activate bash)\"" > /etc/profile.d/mise.sh && \
    echo "eval \"\$(/usr/local/bin/mise activate zsh)\"" > /etc/profile.d/mise.zsh

WORKDIR /workspaces
