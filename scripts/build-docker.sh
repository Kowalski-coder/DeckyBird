#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="deckybird-steamos-builder:ubuntu24.04"

echo "==> Building Docker image $IMAGE_NAME..."
docker build -t "$IMAGE_NAME" -f "$ROOT_DIR/docker/Dockerfile.steamos-build" "$ROOT_DIR"

echo "==> Running Ladybird Distribution build inside Ubuntu 24.04 container..."
docker run --rm -it \
    -v "$ROOT_DIR:/workspace" \
    -w /workspace/ladybird \
    "$IMAGE_NAME" \
    bash -c '
        set -euo pipefail
        if [ ! -f /tmp/.deps_installed ]; then
            ./Meta/Docker/ci/install-build-dependencies.sh
            touch /tmp/.deps_installed
        fi
        cmake --preset Distribution -B Build
        cmake --build Build --parallel "$(nproc)"
    '
