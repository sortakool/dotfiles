# syntax=docker/dockerfile:1.7

# ============================================================
# Composable base image: ubuntu (default) or cpp-devcontainer
# ============================================================
ARG BASE_IMAGE=ubuntu:25.10

FROM ${BASE_IMAGE} AS base

ARG DEBIAN_FRONTEND=noninteractive
ARG APT_SNAPSHOT=20260328T000000Z
ARG MISE_VERSION=2026.3.10
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=${USER_UID}

ENV DEBIAN_FRONTEND=${DEBIAN_FRONTEND} \
    MISE_STRICT=1

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# APT snapshot pinning for reproducible builds
# Cache scoped by APT_SNAPSHOT to prevent cross-target cache poisoning
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

# Bare minimum system dependencies (everything else via mise/pixi/uv)
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

# ---------- user setup ----------
FROM base AS user-setup

ARG USERNAME
ARG USER_UID
ARG USER_GID

RUN export USER_UID=${USER_UID:-1000} \
    && export USER_GID=${USER_GID:-$USER_UID} \
    && if id -u $USERNAME >/dev/null 2>&1; then userdel -r $USERNAME || true; fi \
    && if getent group $USERNAME >/dev/null 2>&1; then groupdel $USERNAME || true; fi \
    && if id -u 1000 >/dev/null 2>&1; then userdel -r $(id -nu 1000) || true; fi \
    && if getent group 1000 >/dev/null 2>&1; then groupdel $(getent group 1000 | cut -d: -f1) || true; fi \
    && if id -u $USER_UID >/dev/null 2>&1; then userdel -r $(id -nu $USER_UID) || true; fi \
    && if getent group $USER_GID >/dev/null 2>&1; then groupdel $(getent group $USER_GID | cut -d: -f1) || true; fi \
    && groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m -s /bin/bash $USERNAME \
    && mkdir -p /home/$USERNAME/.ssh && chmod 700 /home/$USERNAME/.ssh \
    && chown $USERNAME:$USERNAME /home/$USERNAME/.ssh \
    && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# ---------- mise system install ----------
FROM user-setup AS mise-setup

ARG USERNAME

# Install pinned mise version globally (survives home directory volume mounts)
ARG MISE_VERSION
RUN curl -fsSL "https://mise.jdx.dev/v${MISE_VERSION}/mise-v${MISE_VERSION}-linux-x64" \
      -o /usr/local/bin/mise \
    && chmod 755 /usr/local/bin/mise

# ---------- final ----------
FROM mise-setup AS final

ARG USERNAME

USER $USERNAME
ENV USER=$USERNAME \
    PATH="/home/$USERNAME/.local/bin:/home/$USERNAME/.local/share/mise/shims:/home/$USERNAME/.cargo/bin:/usr/local/bin:${PATH}"

WORKDIR /home/$USERNAME

# Copy dotfiles repository for chezmoi
COPY --chown=$USERNAME:$USERNAME . /home/$USERNAME/.local/share/chezmoi

WORKDIR /home/$USERNAME
