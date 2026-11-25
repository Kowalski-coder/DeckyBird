#!/usr/bin/env bash
set -euo pipefail

# Скачивает последний официальный релиз Ladybird (Ubuntu 24.04 amd64 .deb)
# в папку Update/Original/ предварительно очистив её.
# Можно передать конкретную версию первым аргументом, например:
#   ./download_original.sh 2026.47.8

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORIG_DIR="$SCRIPT_DIR/Original"
RELEASES_URL="https://download.ladybird.org/releases.json"
REQ_VERSION="${1:-}"

mkdir -p "$ORIG_DIR"
echo "==> Очистка $ORIG_DIR..."
rm -rf "${ORIG_DIR:?}"/*

echo "==> Получение информации о релизах Ladybird ($RELEASES_URL)..."
META_JSON="$(curl -fsSL "$RELEASES_URL")"

read -r VERSION DL_URL PKG_NAME < <(python3 -c '
import json, sys
data = json.loads(sys.stdin.read())
req = sys.argv[1] if len(sys.argv) > 1 else ""
releases = data.get("releases", [])
target = None
for r in releases:
    if not req or r.get("version") == req:
        target = r
        break
if not target:
    label = req or "latest"
    sys.stderr.write(f"Ошибка: релиз {label} не найден в releases.json\n")
    sys.exit(1)
ver = target["version"]
for d in target.get("downloads", []):
    if d.get("platform") == "Linux" and d.get("architecture") == "amd64" and "ubuntu24.04" in d.get("name", ""):
        print(ver, d["url"], d["name"])
        sys.exit(0)
sys.stderr.write(f"Ошибка: пакет ubuntu24.04 amd64 не найден для версии {ver}\n")
sys.exit(1)
' "$REQ_VERSION" <<< "$META_JSON")

echo "==> Найдена версия: $VERSION ($PKG_NAME)"
echo "==> Скачивание: $DL_URL"
curl -fSL --progress-bar -o "$ORIG_DIR/$PKG_NAME" "$DL_URL"
echo "$VERSION" > "$ORIG_DIR/VERSION"

echo "==> Готово! Оригинал сохранён в: $ORIG_DIR/$PKG_NAME"
ls -lh "$ORIG_DIR"
