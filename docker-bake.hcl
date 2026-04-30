variable "DEFAULT_REGISTRY" {
  default = "ghcr.io/ray-manaloto"
}

variable "IMAGE" {
  default = "dotfiles-devcontainer"
}

# Full image reference used for tags and cache refs
# In CI, metadata-action overrides tags; this controls cache and local builds
variable "IMAGE_REF" {
  default = "${DEFAULT_REGISTRY}/${IMAGE}"
}

variable "TAG" {
  default = "dev"
}

variable "PLATFORM" {
  default = "linux/amd64/v2"
}

variable "BASE_IMAGE" {
  default = "ubuntu:26.04"
}

variable "DEVCONTAINER_USERNAME" {
  default = "devcontainer"
}

# Pinned commit SHA for Bloomberg's clang-p2996 fork (C++ P2996 reflection).
# Changing this value invalidates the BuildKit cache for the clang-builder stage.
variable "CLANG_P2996_REF" {
  default = "9ffb96e3ce362289008e14ad2a79a249f58aa90a"
}

// Default tags for local builds; overridden by docker/metadata-action
// bake files in CI to inject SHA, latest, and PR tags.
target "docker-metadata-action" {
  tags = [
    "${IMAGE_REF}:${TAG}",
  ]
}

target "_common" {
  context    = "."
  dockerfile = ".devcontainer/Dockerfile"
  platforms  = ["${PLATFORM}"]
  args = {
    DEVCONTAINER_USERNAME = DEVCONTAINER_USERNAME
  }
  secret = [
    "id=github_token,env=GITHUB_TOKEN",
  ]
}

# Default dev environment on ubuntu base.
# CI's base-prep + p2996-prep jobs override DEVCONTAINER_BASE_REF and
# P2996_SOURCE with published cache image refs so the dev build is a
# pull + thin layer instead of rebuilding base + clang from scratch.
target "dev" {
  inherits = ["_common", "docker-metadata-action"]
  target   = "devcontainer"
  args = {
    BASE_IMAGE      = BASE_IMAGE
    CLANG_P2996_REF = CLANG_P2996_REF
    # Defaults are local stage names — cold path. CI overrides these.
    DEVCONTAINER_BASE_REF = "devcontainer-base"
    P2996_SOURCE          = "p2996-export"
  }
  # Tags inherited from docker-metadata-action (CI overrides with SHA/latest/PR tags)
  cache-from = [
    "type=gha,scope=dotfiles-dev",
  ]
  cache-to = [
    "type=gha,scope=dotfiles-dev,mode=max",
  ]
  attest = [
    "type=provenance,mode=min",
    "type=sbom",
  ]
}

# Content-addressed cache for the devcontainer-base stage (apt + mise
# install + cargo crates — the heavy ~30 min layer). CI tags it
# ghcr.io/<owner>/<repo>:base-<hash16> where the hash captures
# BASE_IMAGE + Dockerfile base-section + mise-system-resolved.json.
# Both p2996-cache and dev pull this image so neither rebuilds the
# mise install when only p2996 inputs change.
target "base" {
  inherits = ["_common"]
  target   = "devcontainer-base"
  args = {
    BASE_IMAGE = BASE_IMAGE
  }
  cache-from = [
    "type=gha,scope=dotfiles-base",
  ]
  cache-to = [
    "type=gha,scope=dotfiles-base,mode=max",
  ]
}

# Content-addressed cache for the clang-p2996 build artifact.
# Builds only the scratch-based p2996-export stage (~500 MB, just
# /opt/clang-p2996/). CI passes DEVCONTAINER_BASE_REF=
# ghcr.io/.../:base-<base-hash16> so the mise install layer is pulled
# (not rebuilt) before the clang compile starts. Tag pattern:
# ghcr.io/<owner>/<repo>:p2996-<p2996-hash16>.
target "p2996-cache" {
  inherits = ["_common"]
  target   = "p2996-export"
  args = {
    BASE_IMAGE            = BASE_IMAGE
    CLANG_P2996_REF       = CLANG_P2996_REF
    DEVCONTAINER_BASE_REF = "devcontainer-base"
  }
  cache-from = [
    "type=gha,scope=dotfiles-p2996-cache",
  ]
  cache-to = [
    "type=gha,scope=dotfiles-p2996-cache,mode=max",
  ]
}

# Local-load variant (outputs to docker instead of registry)
target "dev-load" {
  inherits = ["dev"]
  output   = ["type=docker"]
  tags     = ["${IMAGE_REF}:${TAG}"]
}

# Validation target (dry-run mode)
target "validate" {
  inherits = ["dev"]
  call     = "check"
}

# Introspection target (lists all targets)
target "help" {
  call = "targets"
}

group "default" {
  targets = ["dev"]
}

group "all" {
  targets = ["dev"]
}
