variable "DEFAULT_REGISTRY" {
  default = "ghcr.io/sortakool"
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

variable "CPP_BASE_IMAGE" {
  default = "${DEFAULT_REGISTRY}/cpp-devcontainer:dev"
}

variable "APT_SNAPSHOT" {
  default = "20260328T000000Z"
}

variable "DEVCONTAINER_USERNAME" {
  default = "vscode"
}

target "_common" {
  context    = "."
  dockerfile = ".devcontainer/Dockerfile"
  platforms  = ["${PLATFORM}"]
  args = {
    APT_SNAPSHOT = APT_SNAPSHOT
    USERNAME     = DEVCONTAINER_USERNAME
  }
}

# Default dev environment on ubuntu base
target "dev" {
  inherits = ["_common"]
  target   = "final"
  args = {
    BASE_IMAGE   = BASE_IMAGE
    APT_SNAPSHOT = APT_SNAPSHOT
  }
  tags = [
    "${IMAGE_REF}:${TAG}",
  ]
  # Registry cache: shared across CI runs and local dev
  # GHA cache: faster for same-repo CI (set ACTIONS_CACHE_URL to enable)
  cache-from = [
    "type=registry,ref=${IMAGE_REF}:buildcache",
    "type=gha,scope=dotfiles-dev",
  ]
  cache-to = [
    "type=registry,ref=${IMAGE_REF}:buildcache,mode=max",
    "type=gha,scope=dotfiles-dev,mode=max",
  ]
  attest = [
    "type=provenance,mode=min",
    "type=sbom",
  ]
}

# C++ variant using cpp-playground's published image as base
target "cpp" {
  inherits = ["_common"]
  target   = "final"
  args = {
    BASE_IMAGE   = CPP_BASE_IMAGE
    APT_SNAPSHOT = APT_SNAPSHOT
  }
  tags = [
    "${IMAGE_REF}:cpp-${TAG}",
  ]
  cache-from = [
    "type=registry,ref=${IMAGE_REF}:cpp-buildcache",
    "type=gha,scope=dotfiles-cpp",
  ]
  cache-to = [
    "type=registry,ref=${IMAGE_REF}:cpp-buildcache,mode=max",
    "type=gha,scope=dotfiles-cpp,mode=max",
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
  tags     = ["${IMAGE_REF}:${TAG}", "${IMAGE}:${TAG}"]
}

target "cpp-load" {
  inherits = ["cpp"]
  output   = ["type=docker"]
  tags     = ["${IMAGE_REF}:cpp-${TAG}", "${IMAGE}:cpp-${TAG}"]
}

group "default" {
  targets = ["dev"]
}

group "all" {
  targets = ["dev", "cpp"]
}
