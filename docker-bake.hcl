variable "REGISTRY" {
  default = "ghcr.io/ray-manaloto"
}

variable "IMAGE" {
  default = "dotfiles-devcontainer"
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
  default = "ghcr.io/ray-manaloto/cpp-devcontainer:dev"
}

variable "APT_SNAPSHOT" {
  default = "20260328T000000Z"
}

variable "MISE_VERSION" {
  default = "2026.3.10"
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
    MISE_VERSION = MISE_VERSION
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
    USERNAME     = DEVCONTAINER_USERNAME
  }
  tags = [
    "${REGISTRY}/${IMAGE}:${TAG}",
    "${IMAGE}:${TAG}",
  ]
  cache-from = [
    "type=registry,ref=${REGISTRY}/${IMAGE}:buildcache",
  ]
  cache-to = [
    "type=registry,ref=${REGISTRY}/${IMAGE}:buildcache,mode=max",
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
    USERNAME     = DEVCONTAINER_USERNAME
  }
  tags = [
    "${REGISTRY}/${IMAGE}:cpp-${TAG}",
    "${IMAGE}:cpp-${TAG}",
  ]
  cache-from = [
    "type=registry,ref=${REGISTRY}/${IMAGE}:cpp-buildcache",
  ]
  cache-to = [
    "type=registry,ref=${REGISTRY}/${IMAGE}:cpp-buildcache,mode=max",
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
}

target "cpp-load" {
  inherits = ["cpp"]
  output   = ["type=docker"]
}

group "default" {
  targets = ["dev"]
}

group "all" {
  targets = ["dev", "cpp"]
}
