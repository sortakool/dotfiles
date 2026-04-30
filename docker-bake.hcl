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

# Default dev environment on ubuntu base
target "dev" {
  inherits = ["_common", "docker-metadata-action"]
  target   = "devcontainer"
  args = {
    BASE_IMAGE      = BASE_IMAGE
    CLANG_P2996_REF = CLANG_P2996_REF
    # Default cold-build path. CI's p2996-prep job overrides this with
    # ghcr.io/<owner>/<repo>:p2996-<hash16> on cache hit, skipping the
    # ~80–120 min clang compile entirely. See p2996-cache target.
    P2996_SOURCE = "p2996-export"
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

# Content-addressed cache for the clang-p2996 build artifact.
# Builds only the scratch-based p2996-export stage (~500 MB, just
# /opt/clang-p2996/). CI tags it ghcr.io/<owner>/<repo>:p2996-<hash16>
# where the hash captures CLANG_P2996_REF + Dockerfile + bake-vars +
# .devcontainer/mise-system-resolved.json. On hash hit, dev target
# uses this image as P2996_SOURCE and skips the cold compile.
target "p2996-cache" {
  inherits = ["_common"]
  target   = "p2996-export"
  args = {
    BASE_IMAGE      = BASE_IMAGE
    CLANG_P2996_REF = CLANG_P2996_REF
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
