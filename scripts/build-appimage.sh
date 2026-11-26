#!/usr/bin/env bash
set -euo pipefail

# Packages DeckyBird AppImage from:
#   1) An official Ladybird Ubuntu 24.04 .deb package
#   2) An existing Ladybird .AppImage
#   3) A built ladybird/Build directory
#
# Usage:
#   ./scripts/build-appimage.sh [path/to/ladybird.deb|Ladybird.AppImage] [output_name]

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/dist"
mkdir -p "$OUT_DIR"

INPUT_PKG="${1:-}"
OUT_NAME="${2:-DeckyBirdTest.AppImage}"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

APPDIR="$WORK_DIR/AppDir"
mkdir -p "$APPDIR/usr"

if [[ "$INPUT_PKG" == *.deb ]]; then
    echo "==> Unpacking Ladybird .deb: $INPUT_PKG"
    mkdir -p "$WORK_DIR/deb"
    (cd "$WORK_DIR/deb" && ar x "$(realpath "$INPUT_PKG")" && tar -xf data.tar.*)
    if [ -d "$WORK_DIR/deb/opt/ladybird" ]; then
        cp -a "$WORK_DIR/deb/opt/ladybird"/* "$APPDIR/usr/"
    else
        cp -a "$WORK_DIR/deb/usr"/* "$APPDIR/usr/"
    fi
elif [ -n "$INPUT_PKG" ]; then
    echo "==> Unpacking base AppImage: $INPUT_PKG"
    chmod +x "$INPUT_PKG"
    (cd "$WORK_DIR" && "$(realpath "$INPUT_PKG")" --appimage-extract >/dev/null)
    rm -rf "$APPDIR"
    mv "$WORK_DIR/squashfs-root" "$APPDIR"
else
    BUILD_DIR="$ROOT_DIR/ladybird/Build"
    if [ ! -d "$BUILD_DIR" ]; then
        echo "Error: $BUILD_DIR not found and no .deb/.AppImage provided." >&2
        exit 1
    fi
    echo "==> Packaging base AppDir from $BUILD_DIR..."
    "$ROOT_DIR/ladybird/Meta/package-appimage.sh" "$BUILD_DIR" "dev" "x86_64" "$WORK_DIR"
    BASE_IMG="$(find "$WORK_DIR" -maxdepth 1 -name '*.AppImage' | head -n 1)"
    chmod +x "$BASE_IMG"
    (cd "$WORK_DIR" && "$BASE_IMG" --appimage-extract >/dev/null)
    rm -rf "$APPDIR"
    mv "$WORK_DIR/squashfs-root" "$APPDIR"
fi

echo "==> Applying DeckyBird root overlay..."
cp -af "$ROOT_DIR/overlay/root"/* "$APPDIR/"
chmod +x "$APPDIR/AppRun"
if [ -f "$APPDIR/deckybird.png" ]; then
    cp -f "$APPDIR/deckybird.png" "$APPDIR/.DirIcon"
    mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps" "$APPDIR/usr/share/icons/hicolor/scalable/apps" "$APPDIR/usr/share/applications"
    cp -f "$APPDIR/deckybird.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/deckybird.png"
    cp -f "$APPDIR/deckybird.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/org.ladybird.Ladybird.png"
    if [ -f "$APPDIR/deckybird.svg" ]; then
        cp -f "$APPDIR/deckybird.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/deckybird.svg"
        cp -f "$APPDIR/deckybird.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/org.ladybird.Ladybird.svg"
    fi
    if [ -f "$APPDIR/net.deckybird.DeckyBird.desktop" ]; then
        cp -f "$APPDIR/net.deckybird.DeckyBird.desktop" "$APPDIR/usr/share/applications/net.deckybird.DeckyBird.desktop"
        cp -f "$APPDIR/net.deckybird.DeckyBird.desktop" "$APPDIR/usr/share/applications/org.ladybird.Ladybird.desktop"
    fi
    if command -v rsvg-convert >/dev/null 2>&1 && [ -f "$APPDIR/deckybird.svg" ]; then
        mkdir -p "$APPDIR/usr/share/Lagom/icons/48x48"
        rsvg-convert -w 48 -h 48 "$APPDIR/deckybird.svg" -o "$APPDIR/usr/share/Lagom/icons/48x48/app-browser.png"
    fi
fi

echo "==> Installing DeckyBird modules..."
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/deckybird/certs" "$APPDIR/usr/share/deckybird/defaults" "$APPDIR/usr/share/deckywolf"

if [ -f "$ROOT_DIR/modules/controller/deckybird-controller" ]; then
    cp -f "$ROOT_DIR/modules/controller/deckybird-controller" "$APPDIR/usr/bin/"
    chmod +x "$APPDIR/usr/bin/deckybird-controller"
fi

if [ -f "$ROOT_DIR/modules/torrent/deckybird-torrent-service" ]; then
    cp -f "$ROOT_DIR/modules/torrent/deckybird-torrent-service" "$APPDIR/usr/bin/"
    chmod +x "$APPDIR/usr/bin/deckybird-torrent-service"
fi

if [ -d "$ROOT_DIR/modules/torrent/plugins" ]; then
    cp -a "$ROOT_DIR/modules/torrent/plugins" "$APPDIR/usr/share/deckywolf/"
    if command -v zip >/dev/null 2>&1 && [ -d "$APPDIR/usr/share/deckywolf/plugins/TorrentWolf" ]; then
        (cd "$APPDIR/usr/share/deckywolf/plugins" && zip -q -r TorrentWolf.zip TorrentWolf)
    fi
fi

if [ -d "$ROOT_DIR/modules/torrent/torrent" ]; then
    cp -a "$ROOT_DIR/modules/torrent/torrent" "$APPDIR/usr/share/deckywolf/"
fi

if [ -f "$ROOT_DIR/modules/decky-bridge/deckybird-bridge.py" ]; then
    cp -f "$ROOT_DIR/modules/decky-bridge/deckybird-bridge.py" "$APPDIR/usr/bin/deckybird-bridge"
    chmod +x "$APPDIR/usr/bin/deckybird-bridge"
fi

if [ -f "$ROOT_DIR/modules/decky-bridge/decky_page_script.js" ]; then
    cp -f "$ROOT_DIR/modules/decky-bridge/decky_page_script.js" "$APPDIR/usr/share/deckybird/decky_page_script.js"
fi

if [ -d "$ROOT_DIR/modules/webapps" ]; then
    mkdir -p "$APPDIR/usr/share/deckybird/webapps"
    cp -af "$ROOT_DIR/modules/webapps"/* "$APPDIR/usr/share/deckybird/webapps/"
    if [ -f "$ROOT_DIR/modules/webapps/deckybird_webapp_manager.py" ]; then
        cp -f "$ROOT_DIR/modules/webapps/deckybird_webapp_manager.py" "$APPDIR/usr/bin/deckybird-webapp-manager"
        chmod +x "$APPDIR/usr/bin/deckybird-webapp-manager"
    fi
fi

if [ -d "$ROOT_DIR/modules/extensions" ]; then
    mkdir -p "$APPDIR/usr/share/deckybird/extensions"
    cp -af "$ROOT_DIR/modules/extensions"/* "$APPDIR/usr/share/deckybird/extensions/"
fi

if [ -f "$ROOT_DIR/modules/ui-hook/deckybird-ui-hook.so" ]; then
    mkdir -p "$APPDIR/usr/lib"
    cp -f "$ROOT_DIR/modules/ui-hook/deckybird-ui-hook.so" "$APPDIR/usr/lib/deckybird-ui-hook.so"
fi

if [ -d "$ROOT_DIR/modules/certs" ]; then
    cp -f "$ROOT_DIR/modules/certs"/*.crt "$APPDIR/usr/share/deckybird/certs/" 2>/dev/null || true
fi

if [ -d "$ROOT_DIR/modules/defaults" ]; then
    cp -f "$ROOT_DIR/modules/defaults"/*.json "$APPDIR/usr/share/deckybird/defaults/" 2>/dev/null || true
fi

if [ -f "$ROOT_DIR/modules/startpage/newtab.html" ]; then
    mkdir -p "$APPDIR/usr/share/Lagom/ladybird/about-pages"
    cp -af "$ROOT_DIR/modules/startpage"/* "$APPDIR/usr/share/Lagom/ladybird/about-pages/"
fi

# i18n module (Russian UI for about-pages + Qt menus LD_PRELOAD hook)
if [ -f "$ROOT_DIR/modules/i18n/deckybird-i18n.so" ]; then
    mkdir -p "$APPDIR/usr/lib"
    cp -f "$ROOT_DIR/modules/i18n/deckybird-i18n.so" "$APPDIR/usr/lib/deckybird-i18n.so"
fi

if [ -f "$ROOT_DIR/modules/i18n/deckybird-i18n.js" ]; then
    PAGES_DIR="$APPDIR/usr/share/Lagom/ladybird/about-pages"
    mkdir -p "$PAGES_DIR"
    cp -f "$ROOT_DIR/modules/i18n/deckybird-i18n.js" "$PAGES_DIR/deckybird-i18n.js"
    for page in settings.html bookmarks.html downloads.html history.html crashes.html version.html; do
        if [ -f "$PAGES_DIR/$page" ] && ! grep -q "deckybird-i18n.js" "$PAGES_DIR/$page"; then
            python3 -c "
p = '$PAGES_DIR/$page'
with open(p, 'r', encoding='utf-8') as f:
    s = f.read()
tag = '<script src=\"resource://ladybird/about-pages/deckybird-i18n.js\"></script>'
if '</body>' in s:
    s = s.replace('</body>', tag + '\n</body>', 1)
else:
    s += '\n' + tag + '\n'
with open(p, 'w', encoding='utf-8') as f:
    f.write(s)
"
        fi
    done
fi

OUT_APPIMAGE="$OUT_DIR/$OUT_NAME"
echo "==> Building $OUT_APPIMAGE..."
rm -f "$OUT_APPIMAGE"
chmod -R a+rX "$APPDIR"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 appimagetool --no-appstream "$APPDIR" "$OUT_APPIMAGE"
chmod +x "$OUT_APPIMAGE"
echo "==> Done: $OUT_APPIMAGE"
ls -lh "$OUT_APPIMAGE"
