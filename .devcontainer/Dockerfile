# syntax=docker/dockerfile:1.7
# check=error=true

ARG BASE_IMAGE=ubuntu:26.04

FROM ${BASE_IMAGE} AS devcontainer-base

ARG DEBIAN_FRONTEND=noninteractive

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
#
# Rust cookbook (https://mise.jdx.dev/lang/rust.html):
#   - MISE_CARGO_HOME / MISE_RUSTUP_HOME are mise-specific build-time
#     vars that isolate mise's bundled rust install from the standard
#     CARGO_HOME / RUSTUP_HOME a user might set at runtime.
#   - Standard CARGO_HOME / RUSTUP_HOME are intentionally UNSET so
#     runtime users fall back to ~/.cargo / ~/.rustup defaults; PR-2
#     mounts named volumes there for per-clone persistence and
#     cookbook shadow-priority semantics.
ENV MISE_DATA_DIR=/usr/local/share/mise \
    MISE_CONFIG_DIR=/usr/local/share/mise \
    MISE_INSTALL_PATH=/usr/local/bin/mise \
    MISE_SYSTEM_CONFIG_DIR=/usr/local/share/mise \
    MISE_SYSTEM_CONFIG_FILE=/usr/local/share/mise/config.toml \
    MISE_TRUSTED_CONFIG_PATHS=/usr/local/share/mise:/workspaces/dotfiles \
    MISE_CARGO_HOME=/usr/local/share/cargo \
    MISE_RUSTUP_HOME=/usr/local/share/rustup \
    PATH="/usr/local/bin:/usr/local/share/mise/shims:/usr/local/share/cargo/bin:${PATH}"

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

# Install latest mise via the official installer. Image is rebuilt on
# every `main` push, so CDN drift is acceptable here. The mise.run
# installer already chmods the binary; the explicit chmod is a belt-
# and-braces guard against permission drift on the cache mount.
RUN curl https://mise.run | sh && \
    chmod +x ${MISE_INSTALL_PATH} && \
    mise --version

# System-wide mise config and data structure (cookbook canonical paths).
RUN groupadd --gid 2000 mise && \
    mkdir -p /usr/local/share/mise /usr/local/share/cargo /usr/local/share/rustup && \
    chown -R :mise /usr/local/share/mise /usr/local/share/cargo /usr/local/share/rustup && \
    chmod -R 775 /usr/local/share/mise /usr/local/share/cargo /usr/local/share/rustup

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
    mise install --system -y && \
    test "$(mise ls --installed | wc -l)" -gt 0 || { echo "ERROR: mise installed zero tools — system config not discovered (check MISE_CONFIG_DIR points at /usr/local/share/mise containing config.toml)"; exit 1; } && \
    test -d /usr/local/share/cargo/bin || { echo "ERROR: MISE_CARGO_HOME not honored — /usr/local/share/cargo/bin missing after mise install (rust cookbook regression)"; exit 1; } && \
    test -d /usr/local/share/rustup/toolchains || { echo "ERROR: MISE_RUSTUP_HOME not honored — /usr/local/share/rustup/toolchains missing after mise install (rust cookbook regression)"; exit 1; } && \
    chmod -R 777 /usr/local/share/mise /usr/local/share/cargo /usr/local/share/rustup

# Reshim to ensure all shims are present (aqua tools may include doc-file
# shims like LICENSE, README — these are harmless and must not be deleted
# or mise doctor will report them as missing)
RUN mise reshim -f && \
    test -n "$(find /usr/local/share/mise/shims -mindepth 1 -maxdepth 1 -print -quit)" || { echo "ERROR: /usr/local/share/mise/shims empty after reshim — mise has no installed tools to shim"; exit 1; }

# Final global permissions check
RUN chmod -R 777 /usr/local/share/mise /usr/local/share/cargo /usr/local/share/rustup

# Copy image-specific hk config + shared checks for smoke-test validation.
# hk-image.pkl imports hk-common.pkl — both must be in /etc/hk/ for pkl
# relative import resolution. hk-image.pkl is renamed to hk.pkl (hk default).
COPY hk-common.pkl /etc/hk/hk-common.pkl
COPY hk-image.pkl /etc/hk/hk.pkl

# Ensure mise is activated for all users
RUN echo "eval \"\$(/usr/local/bin/mise activate bash)\"" > /etc/profile.d/mise.sh && \
    echo "eval \"\$(/usr/local/bin/mise activate zsh)\"" > /etc/profile.d/mise.zsh

WORKDIR /workspaces

# ── clang-p2996 builder (Bloomberg fork, built from source) ──────────
# Runs in parallel with devcontainer-base via BuildKit DAG.
# Only the install prefix (/opt/clang-p2996) is COPY'd into the final
# stage — the ~20GB build tree is discarded.
#
# Three-stage pattern:
#   1. clang-builder-cold: heavy compile from source (~80–120 min cold)
#   2. p2996-export: scratch-based export of just /opt/clang-p2996
#      (~500 MB — small enough for cheap GHCR push/pull as cache image)
#   3. clang-builder: indirection layer; FROM ${P2996_SOURCE} resolves
#      to either the local p2996-export (cold path) or to a pre-built
#      cache image like ghcr.io/<owner>/<repo>:p2996-<hash16>.
#
# The dev target passes P2996_SOURCE=p2996-export by default; CI's
# p2996-prep job overrides it with the cache image ref on hash hit.
FROM devcontainer-base AS clang-builder-cold

ARG DEBIAN_FRONTEND=noninteractive
ARG CLANG_P2996_REPO=https://github.com/bloomberg/clang-p2996.git
ARG CLANG_P2996_REF=9ffb96e3ce362289008e14ad2a79a249f58aa90a

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && apt-get install -y --no-install-recommends \
      libedit-dev \
      libffi-dev \
      libncurses5-dev \
      libxml2-dev \
      libzstd-dev \
      swig

WORKDIR /opt/clang-p2996

RUN git init . && \
    git remote add origin "${CLANG_P2996_REPO}" && \
    git fetch --depth 1 origin "${CLANG_P2996_REF}" && \
    git checkout FETCH_HEAD

WORKDIR /opt/clang-p2996/build

# cmake and ninja are available via mise shims from devcontainer-base.
# Build only X86 target to minimize compile time and binary size.
# ccache mount persists across builds — on SHA change, ~80% of objects
# are reusable, cutting rebuild time significantly vs cold cache.
# See issue #82 for further caching optimization (sccache, separate scope).
RUN --mount=type=cache,target=/root/.cache/ccache,sharing=locked \
    cmake -G Ninja ../llvm \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX=/opt/clang-p2996 \
      -DCMAKE_C_COMPILER=gcc \
      -DCMAKE_CXX_COMPILER=g++ \
      -DLLVM_ENABLE_PROJECTS="clang;lld" \
      -DLLVM_ENABLE_RUNTIMES="libcxx;libcxxabi;libunwind" \
      -DLLVM_TARGETS_TO_BUILD=X86 \
      -DLLVM_CCACHE_BUILD=ON \
      -DLLVM_ENABLE_BINDINGS=OFF \
      -DLLVM_ENABLE_TERMINFO=OFF \
      -DLLVM_INCLUDE_BENCHMARKS=OFF \
      -DLLVM_INCLUDE_EXAMPLES=OFF \
      -DLLVM_INCLUDE_TESTS=OFF \
      -DCLANG_DEFAULT_CXX_STDLIB=libc++ && \
    ninja install

# Smoke test: verify clang-p2996 can parse reflection headers.
# Runs only on the cold compile path; cached pulls inherit this validation.
RUN printf '#include <meta>\nint main(){return 0;}\n' >/tmp/refl.cpp && \
    /opt/clang-p2996/bin/clang++ \
      -std=c++2c \
      -freflection \
      -freflection-latest \
      -fexpansion-statements \
      -stdlib=libc++ \
      /tmp/refl.cpp \
      -fsyntax-only && \
    rm -f /tmp/refl.cpp

# ── p2996-export: tiny scratch-based image holding just the install prefix.
# This is what gets pushed to GHCR as :p2996-<hash16> for cross-build reuse.
FROM scratch AS p2996-export
COPY --from=clang-builder-cold /opt/clang-p2996 /opt/clang-p2996

# ── clang-builder: thin indirection that switches between cold-build
# (FROM p2996-export, which transitively builds clang-builder-cold)
# and cache-pull (FROM ghcr.io/.../:p2996-<hash16>). Whichever the bake
# arg P2996_SOURCE resolves to, the resulting stage exposes
# /opt/clang-p2996 for the final COPY below.
ARG P2996_SOURCE=p2996-export
FROM ${P2996_SOURCE} AS clang-builder

# ── final: combine base + reflection compilers ───────────────────────
# Stage name "devcontainer" preserves docker-bake.hcl target and
# Dockerfile.host-user BASE_IMAGE compatibility — no downstream changes.
FROM devcontainer-base AS devcontainer

# GCC-16 with P2996 reflection (precompiled .deb from jwakely trunk snapshot,
# post-reflection-merge commit 4b0e94b 2026-01-15).
# Installs to /opt/gcc-latest/bin. Rolling latest — no pinned hash.
# kayari.org ships a single rolling .deb tracking Ubuntu trunk; compatibility
# with the current base image is empirical. If `dpkg -i` fails, build from
# source (see cpp-playground Dockerfile gcc stage for the pattern).
RUN curl -fLOSs https://kayari.org/gcc-latest/gcc-latest.deb && \
    dpkg -i gcc-latest.deb && \
    rm -f gcc-latest.deb && \
    test -x /opt/gcc-latest/bin/g++ || { echo "ERROR: gcc-latest binary missing after dpkg install"; exit 1; }

# clang-p2996 (Bloomberg fork, built from source in clang-builder stage)
COPY --from=clang-builder /opt/clang-p2996 /opt/clang-p2996

# Add reflection compilers to PATH; LD_RUN_PATH for gcc-latest runtime libs
ENV PATH="/opt/gcc-latest/bin:/opt/clang-p2996/bin:${PATH}" \
    LD_RUN_PATH="/opt/gcc-latest/lib64"

# Smoke test: GCC-16 reflection
RUN printf '#include <meta>\nint main(){return 0;}\n' >/tmp/refl-gcc.cpp && \
    /opt/gcc-latest/bin/g++ \
      -std=c++26 \
      -freflection \
      /tmp/refl-gcc.cpp \
      -fsyntax-only && \
    rm -f /tmp/refl-gcc.cpp

# Smoke test: clang-p2996 reflection
RUN printf '#include <meta>\nint main(){return 0;}\n' >/tmp/refl-clang.cpp && \
    /opt/clang-p2996/bin/clang++ \
      -std=c++2c \
      -freflection \
      -freflection-latest \
      -fexpansion-statements \
      -stdlib=libc++ \
      /tmp/refl-clang.cpp \
      -fsyntax-only && \
    rm -f /tmp/refl-clang.cpp
