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
  default = "linux/amd64"
}

variable "BASE_IMAGE" {
  default = "ubuntu:25.10"
}

variable "MISE_VERSION" {
  default = "v2026.4.5"
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
    MISE_VERSION          = MISE_VERSION
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
