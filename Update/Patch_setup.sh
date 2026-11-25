#!/usr/bin/env bash
set -euo pipefail

# Применяет все модули и оверлеи DeckyBird к оригиналу из Update/Original/
# и собирает готовый к публикации DeckyBird.AppImage в Update/DeckyBird/.
#
# Использование:
#   ./Patch_setup.sh [номер_ревизии_форка]   (по умолчанию 1 -> <orig_ver>.1)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ORIG_DIR="$SCRIPT_DIR/Original"
OUT_DIR="$SCRIPT_DIR/DeckyBird"
FORK_REV="${1:-1}"

ORIG_PKG="$(find "$ORIG_DIR" -maxdepth 1 \( -name '*.deb' -o -name '*.AppImage' \) | head -n 1)"
if [ -z "$ORIG_PKG" ]; then
    echo "Ошибка: в $ORIG_DIR не найден .deb или .AppImage оригинала Ladybird." >&2
    echo "Сначала запустите: ./download_original.sh" >&2
    exit 1
fi

ORIG_VER="unknown"
if [ -f "$ORIG_DIR/VERSION" ]; then
    ORIG_VER="$(tr -d '[:space:]' < "$ORIG_DIR/VERSION")"
fi
FULL_VER="${ORIG_VER}.${FORK_REV}"

mkdir -p "$OUT_DIR"
echo "==> Сборка DeckyBird версии $FULL_VER из $(basename "$ORIG_PKG")..."

"$ROOT_DIR/scripts/build-appimage.sh" "$ORIG_PKG" "DeckyBird.AppImage"
mv -f "$ROOT_DIR/dist/DeckyBird.AppImage" "$OUT_DIR/DeckyBird.AppImage"
chmod +x "$OUT_DIR/DeckyBird.AppImage"
echo "$FULL_VER" > "$OUT_DIR/VERSION"

echo "==> Готово! Релизный файл: $OUT_DIR/DeckyBird.AppImage (версия $FULL_VER)"
ls -lh "$OUT_DIR"
