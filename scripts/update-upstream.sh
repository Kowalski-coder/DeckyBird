#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LADYBIRD_DIR="$ROOT_DIR/ladybird"

if [ ! -d "$LADYBIRD_DIR/.git" ]; then
    echo "Cloning Ladybird into $LADYBIRD_DIR..."
    git clone --depth 1 https://github.com/LadybirdBrowser/ladybird.git "$LADYBIRD_DIR"
    exit 0
fi

echo "==> Resetting local changes in upstream ladybird/ before update..."
git -C "$LADYBIRD_DIR" reset --hard HEAD
git -C "$LADYBIRD_DIR" clean -fd -e Build/

echo "==> Fetching latest upstream Ladybird..."
git -C "$LADYBIRD_DIR" fetch origin master --depth 1
git -C "$LADYBIRD_DIR" checkout -B master origin/master
echo "==> Upstream updated to $(git -C "$LADYBIRD_DIR" rev-parse --short HEAD)"
