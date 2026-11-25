#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LADYBIRD_DIR="$ROOT_DIR/ladybird"
PATCHES_DIR="$ROOT_DIR/patches"

echo "==> Applying DeckyBird patches to $LADYBIRD_DIR..."
shopt -s nullglob
for patch_file in "$PATCHES_DIR"/*.patch; do
    echo "    Applying $(basename "$patch_file")..."
    if git -C "$LADYBIRD_DIR" apply --check "$patch_file" 2>/dev/null; then
        git -C "$LADYBIRD_DIR" apply "$patch_file"
    else
        echo "    [Notice] Patch $(basename "$patch_file") already applied or needs rebase."
    fi
done

# Note: modules/decky-bridge will be linked/copied here once implemented.
echo "==> Done applying modules and patches."
