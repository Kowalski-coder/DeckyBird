#!/usr/bin/env python3
"""
DeckyBird WebApp Manager
Handles creation, launching, KDE menu integration, and Steam shortcut management for WebApps.
"""

import os
import sys
import json
import base64
import struct
import binascii
import re
import urllib.request
import urllib.parse
import shutil
import subprocess
import glob
import time

def _ensure_stdlib_paths():
    patterns = [
        "/usr/lib/python3*/",
        "/usr/lib64/python3*/",
        "/usr/lib/python3*/*-packages/",
    ]
    for pattern in patterns:
        for path in sorted(glob.glob(pattern), reverse=True):
            if path not in sys.path:
                sys.path.append(path)

_ensure_stdlib_paths()

HOME = os.path.expanduser("~")
APPLICATIONS_DIR = os.path.join(HOME, ".local", "share", "applications")
ICONS_DIR = os.path.join(HOME, ".local", "share", "icons")
WEBAPPS_DIR = os.path.join(HOME, ".local", "share", "deckybird-webapps")
DESKTOP_DIRS_DIR = os.path.join(HOME, ".local", "share", "desktop-directories")
MENUS_MERGED_DIR = os.path.join(HOME, ".config", "menus", "applications-merged")
KMENUEDIT_PATH = os.path.join(HOME, ".config", "menus", "applications-kmenuedit.menu")
BIN_DIR = os.path.join(HOME, ".local", "bin")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def decode_vdf(data: bytes):
    i = 0

    def read_str():
        nonlocal i
        end = data.find(b'\x00', i)
        if end == -1:
            end = len(data)
        s = data[i:end].decode('utf-8', 'replace')
        i = end + 1
        return s

    def parse_dict():
        nonlocal i
        res = {}
        while i < len(data):
            tag = data[i]
            i += 1
            if tag == 8:
                break
            name = read_str()
            if tag == 0:
                res[name] = parse_dict()
            elif tag == 1:
                res[name] = read_str()
            elif tag == 2:
                res[name] = struct.unpack('<I', data[i:i + 4])[0]
                i += 4
        return res

    if not data or data[0] != 0:
        return "shortcuts", {}
    i += 1
    root_name = read_str()
    return root_name, parse_dict()


def encode_vdf(root_name: str, d: dict) -> bytes:
    res = bytearray()

    def write_dict(sub_d):
        for k, v in sub_d.items():
            if isinstance(v, dict):
                res.append(0)
                res.extend(str(k).encode('utf-8') + b'\x00')
                write_dict(v)
            elif isinstance(v, str):
                res.append(1)
                res.extend(str(k).encode('utf-8') + b'\x00')
                res.extend(v.encode('utf-8') + b'\x00')
            elif isinstance(v, int):
                res.append(2)
                res.extend(str(k).encode('utf-8') + b'\x00')
                res.extend(struct.pack('<I', v & 0xffffffff))
        res.append(8)

    res.append(0)
    res.extend(root_name.encode('utf-8') + b'\x00')
    write_dict(d)
    res.append(8)
    return bytes(res)


def sanitize_slug(name: str) -> str:
    slug = re.sub(r'[^a-zA-Z0-9_\-]', '', name.lower().replace(' ', '-'))
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug or f"webapp-{int(binascii.crc32(name.encode('utf-8')) & 0xffff)}"


def ensure_kde_webapps_category():
    """Configures KDE Application menu with 'Веб-приложения' category and deckybird icon."""
    os.makedirs(DESKTOP_DIRS_DIR, exist_ok=True)
    os.makedirs(MENUS_MERGED_DIR, exist_ok=True)

    dir_file = os.path.join(DESKTOP_DIRS_DIR, "deckybird-webapps.directory")
    dir_content = """[Desktop Entry]
Type=Directory
Name=Веб-приложения
Name[ru]=Веб-приложения
Name[en]=Web Applications
Name[be]=Вэб-праграмы
Name[uk]=Веб-додатки
Name[de]=Web-Anwendungen
Name[fr]=Applications Web
Name[es]=Aplicaciones Web
Name[it]=Applicazioni Web
Name[pt]=Aplicações Web
Name[zh_CN]=Web 应用程序
Name[ja]=ウェブアプリ
Comment=DeckyBird Web Applications
Comment[ru]=Веб-приложения DeckyBird
Comment[en]=DeckyBird Web Applications
Icon=deckybird
"""
    with open(dir_file, "w", encoding="utf-8") as f:
        f.write(dir_content)

    for merged_dir in (
        MENUS_MERGED_DIR,
        os.path.join(HOME, ".config", "menus", "plasma-applications-merged"),
    ):
        os.makedirs(merged_dir, exist_ok=True)
        menu_file = os.path.join(merged_dir, "deckybird-webapps.menu")
        menu_content = """<!DOCTYPE Menu PUBLIC "-//freedesktop//DTD Menu 1.0//EN"
  "http://www.freedesktop.org/standards/menu-spec/1.0/menu.dtd">
<Menu>
\t<Name>Applications</Name>
\t<Menu>
\t\t<Name>WebApps</Name>
\t\t<Directory>deckybird-webapps.directory</Directory>
\t\t<Include>
\t\t\t<Or>
\t\t\t\t<Category>WebApps</Category>
\t\t\t\t<Category>X-WebApps</Category>
\t\t\t</Or>
\t\t</Include>
\t</Menu>
</Menu>
"""
        with open(menu_file, "w", encoding="utf-8") as f:
            f.write(menu_content)

    if os.path.isfile(KMENUEDIT_PATH):
        try:
            with open(KMENUEDIT_PATH, "r", encoding="utf-8") as f:
                c = f.read()
            if "<Menuname>WebApps</Menuname>" not in c:
                target = "<Menuname>Internet</Menuname>"
                if target in c:
                    c = c.replace(target, target + "\n  <Menuname>WebApps</Menuname>")
                    with open(KMENUEDIT_PATH, "w", encoding="utf-8") as f:
                        f.write(c)
        except Exception as e:
            print(f"[WebAppManager] Note: kmenuedit update error: {e}", file=sys.stderr)

    sycoca = shutil.which("kbuildsycoca6") or shutil.which("kbuildsycoca5")
    if sycoca:
        try:
            subprocess.run([sycoca, "--noincremental"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


def ensure_launcher_script() -> str:
    """Ensures ~/.local/bin/deckybird-webapp-launch exists and is executable."""
    os.makedirs(BIN_DIR, exist_ok=True)
    launcher = os.path.join(BIN_DIR, "deckybird-webapp-launch")
    appimage_hint = os.environ.get("APPIMAGE", "")

    script = f"""#!/usr/bin/env bash
# ==============================================================================
# DeckyBird Web Application Launcher
# ==============================================================================
set -e

APP_ID="$1"
if [ -z "$APP_ID" ]; then
    echo "Usage: deckybird-webapp-launch <app_id>" >&2
    exit 1
fi

APP_DIR="${{HOME}}/.local/share/deckybird-webapps/${{APP_ID}}"
CONFIG_FILE="${{APP_DIR}}/config.json"
PROFILE_DIR="${{APP_DIR}}/profile"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: WebApp config not found at $CONFIG_FILE" >&2
    exit 1
fi

mkdir -p "${{PROFILE_DIR}}/config"
APP_URL=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['url'])")

# Seed Settings.json in profile/config/Settings.json (where Ladybird --profile-path reads it)
DEFAULT_SETTINGS="${{XDG_CONFIG_HOME:-${{HOME}}/.config}}/Ladybird/Profiles/default/Settings.json"
PROFILE_SETTINGS="${{PROFILE_DIR}}/config/Settings.json"
if [ ! -f "$PROFILE_SETTINGS" ]; then
    if [ -f "$DEFAULT_SETTINGS" ]; then
        cp -f "$DEFAULT_SETTINGS" "$PROFILE_SETTINGS" 2>/dev/null || true
    fi
fi
python3 -c "
import json, os
p = '$PROFILE_SETTINGS'
try:
    with open(p, 'r', encoding='utf-8') as f:
        d = json.load(f)
except Exception:
    d = {{}}
d['firstRunComplete'] = True
d['restorePreviousSession'] = False
d['newTabPageURL'] = '$APP_URL'
d.setdefault('configVariables', {{}})['ui.window.use_client_side_decorations'] = False
with open(p, 'w', encoding='utf-8') as f:
    json.dump(d, f)
" 2>/dev/null || true

# If URL is TorrentWolf on localhost, ensure service is running
if [[ "$APP_URL" == *"127.0.0.1:8404"* ]]; then
    if command -v systemctl >/dev/null 2>&1; then
        systemctl --user start deckybird-torrent.service 2>/dev/null || true
    fi
fi

# Find DeckyBird executable
DECKYBIRD_BIN=""
for c in \\
    "${{DECKYBIRD_APPIMAGE:-}}" \\
    "{appimage_hint}" \\
    "${{HOME}}/Desktop/DeckyBird.AppImage" \\
    "${{HOME}}/Desktop/DeckyBirdTest.AppImage" \\
    "${{HOME}}/Desktop/deckybird.AppImage" \\
    "${{HOME}}/Applications/DeckyBird.AppImage" \\
    "${{HOME}}/Applications/DeckyBirdTest.AppImage" \\
    "${{HOME}}/Applications/deckybird.AppImage" \\
    "${{HOME}}/.local/bin/deckybird" \\
    "/usr/bin/deckybird"; do
    if [ -n "$c" ] && [ -x "$c" ]; then
        DECKYBIRD_BIN="$c"
        break
    fi
done

if [ -z "$DECKYBIRD_BIN" ]; then
    # Try finding any DeckyBird*.AppImage on Desktop or Applications
    for c in "${{HOME}}/Desktop"/DeckyBird*.AppImage "${{HOME}}/Applications"/DeckyBird*.AppImage; do
        if [ -x "$c" ]; then
            DECKYBIRD_BIN="$c"
            break
        fi
    done
fi

if [ -z "$DECKYBIRD_BIN" ]; then
    echo "Error: DeckyBird AppImage/binary not found." >&2
    exit 1
fi

export DECKYBIRD_WEBAPP=1
export DECKYBIRD_WEBAPP_ID="$APP_ID"
exec "$DECKYBIRD_BIN" \\
    --profile-path "$PROFILE_DIR" \\
    "$APP_URL"
"""
    with open(launcher, "w", encoding="utf-8") as f:
        f.write(script)
    os.chmod(launcher, 0o755)
    return launcher


def fetch_favicon_bytes(url: str) -> bytes:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.split(":")[0]
    if not domain or domain in ("127.0.0.1", "localhost"):
        return b""
    fav_url = f"https://www.google.com/s2/favicons?domain={urllib.parse.quote(domain)}&sz=128"
    req = urllib.request.Request(fav_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        if resp.status == 200:
            data = resp.read()
            if len(data) > 100:
                return data
    return b""


def _is_internal_browser_url(url: str) -> bool:
    u = (url or "").strip().lower()
    if not u:
        return True
    return (
        u.startswith("about:")
        or u.startswith("resource:")
        or u.startswith("http://127.0.0.1:8406")
        or u.startswith("https://127.0.0.1:8406")
        or u.startswith("http://localhost:8406")
        or u.startswith("https://localhost:8406")
    )


def create_webapp(name: str, url: str, icon_b64: str = None, add_kde: bool = False, add_steam: bool = True) -> dict:
    name = (name or "").strip()
    url = (url or "").strip()
    if not name:
        return {"ok": False, "error": "Имя веб-приложения не может быть пустым"}
    if not url:
        return {"ok": False, "error": "URL веб-приложения не может быть пустым"}
    if _is_internal_browser_url(url):
        return {"ok": False, "error": "Нельзя создать веб-приложение для внутренней страницы браузера"}
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url

    app_id = sanitize_slug(name)
    app_dir = os.path.join(WEBAPPS_DIR, app_id)
    profile_dir = os.path.join(app_dir, "profile")
    os.makedirs(profile_dir, exist_ok=True)

    config = {
        "id": app_id,
        "name": name,
        "url": url,
        "created_at": int(time.time()),
    }
    with open(os.path.join(app_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    icon_dest = os.path.join(app_dir, "icon.png")
    icon_saved = False

    if icon_b64:
        try:
            if "," in icon_b64:
                icon_b64 = icon_b64.split(",", 1)[1]
            raw_bytes = base64.b64decode(icon_b64)
            with open(icon_dest, "wb") as f:
                f.write(raw_bytes)
            icon_saved = True
        except Exception as e:
            print(f"[WebAppManager] Error decoding icon: {e}", file=sys.stderr)

    if not icon_saved and "127.0.0.1:8404" in url:
        for candidate in (
            os.path.expanduser("~/.local/share/deckywolf/torrent/favicon.png"),
            os.path.join(SCRIPT_DIR, "..", "share", "deckywolf", "torrent", "favicon.png"),
        ):
            if os.path.isfile(candidate):
                shutil.copy(candidate, icon_dest)
                icon_saved = True
                break

    if not icon_saved:
        try:
            data = fetch_favicon_bytes(url)
            if data:
                with open(icon_dest, "wb") as f:
                    f.write(data)
                icon_saved = True
        except Exception as e:
            print(f"[WebAppManager] Favicon fetch error: {e}", file=sys.stderr)

    if not icon_saved:
        for candidate in (
            os.path.join(ICONS_DIR, "hicolor", "128x128", "apps", "deckybird.png"),
            os.path.join(ICONS_DIR, "hicolor", "256x256", "apps", "deckybird.png"),
        ):
            if os.path.isfile(candidate):
                shutil.copy(candidate, icon_dest)
                icon_saved = True
                break

    hicolor_128 = os.path.join(ICONS_DIR, "hicolor", "128x128", "apps")
    os.makedirs(hicolor_128, exist_ok=True)
    icon_name = f"deckybird-webapp-{app_id}"
    if os.path.isfile(icon_dest):
        shutil.copy(icon_dest, os.path.join(hicolor_128, f"{icon_name}.png"))
        shutil.copy(icon_dest, os.path.join(ICONS_DIR, f"{icon_name}.png"))

    launcher_path = ensure_launcher_script()

    kde_added = False
    kde_error = ""
    if add_kde:
        try:
            os.makedirs(APPLICATIONS_DIR, exist_ok=True)
            if not os.access(APPLICATIONS_DIR, os.W_OK):
                is_gamescope = bool(os.environ.get("GAMESCOPE_WAYLAND_DISPLAY") or os.environ.get("XDG_CURRENT_DESKTOP") == "gamescope")
                user_name = os.environ.get("USER") or os.path.basename(HOME)
                if not is_gamescope and shutil.which("pkexec"):
                    try:
                        subprocess.run(
                            ["pkexec", "chown", "-R", f"{user_name}:{user_name}", APPLICATIONS_DIR],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=30,
                        )
                    except Exception:
                        pass
                if not os.access(APPLICATIONS_DIR, os.W_OK):
                    raise PermissionError(
                        f"Папка {APPLICATIONS_DIR} принадлежит root. Выполните: sudo chown -R {user_name}:{user_name} {APPLICATIONS_DIR}"
                    )
            ensure_kde_webapps_category()
            desktop_path = os.path.join(APPLICATIONS_DIR, f"deckybird-webapp-{app_id}.desktop")
            desktop_entry = f"""[Desktop Entry]
Type=Application
Name={name}
Comment=Веб-приложение {name} (DeckyBird)
Exec="{launcher_path}" "{app_id}"
Path={app_dir}
Icon={icon_name}
Terminal=false
StartupNotify=true
StartupWMClass=deckybird-webapp-{app_id}
Categories=X-WebApps;WebApps;Network;
"""
            with open(desktop_path, "w", encoding="utf-8") as f:
                f.write(desktop_entry)
            os.chmod(desktop_path, 0o755)

            sycoca = shutil.which("kbuildsycoca6") or shutil.which("kbuildsycoca5")
            if sycoca:
                try:
                    subprocess.run([sycoca, "--noincremental"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
            kde_added = True
        except Exception as e:
            kde_error = str(e)
            print(f"[WebAppManager] KDE desktop entry error: {e}", file=sys.stderr)

    steam_added = False
    if add_steam:
        steam_added = add_to_steam(name, app_id, launcher_path, app_dir, icon_dest)

    return {
        "ok": True,
        "id": app_id,
        "name": name,
        "url": url,
        "kde_added": kde_added,
        "kde_error": kde_error,
        "steam_added": bool(steam_added),
        "message": f"Веб-приложение «{name}» успешно создано!",
    }


def _find_steam_userdata():
    for root in (
        os.path.join(HOME, ".steam", "steam", "userdata"),
        os.path.join(HOME, ".local", "share", "Steam", "userdata"),
    ):
        if os.path.isdir(root):
            return root
    return ""


def add_to_steam(name: str, app_id: str, launcher_path: str, app_dir: str, icon_path: str) -> bool:
    userdata_root = _find_steam_userdata()
    if not userdata_root:
        return False

    crc = binascii.crc32(f'"{launcher_path}"{name}'.encode('utf-8')) | 0x80000000
    user_dirs = [d for d in os.listdir(userdata_root) if os.path.isdir(os.path.join(userdata_root, d)) and d != "0"]
    if not user_dirs:
        return False

    added_any = False
    for u in user_dirs:
        config_dir = os.path.join(userdata_root, u, "config")
        os.makedirs(config_dir, exist_ok=True)
        shortcuts_file = os.path.join(config_dir, "shortcuts.vdf")

        # Copy icons to grid (best-effort)
        grid_dir = os.path.join(config_dir, "grid")
        try:
            os.makedirs(grid_dir, exist_ok=True)
            if os.path.isfile(icon_path):
                shutil.copy(icon_path, os.path.join(grid_dir, f"{crc}_icon.png"))
                shutil.copy(icon_path, os.path.join(grid_dir, f"{crc}.png"))
                shutil.copy(icon_path, os.path.join(grid_dir, f"{crc}p.png"))
        except Exception as e:
            print(f"[WebAppManager] Note: grid icon copy skipped: {e}", file=sys.stderr)

        sc = {}
        root_name = "shortcuts"
        if os.path.isfile(shortcuts_file):
            try:
                with open(shortcuts_file, "rb") as f:
                    root_name, sc = decode_vdf(f.read())
            except Exception:
                sc = {}
            try:
                shutil.copy(shortcuts_file, shortcuts_file + ".deckybird.bak")
            except Exception:
                pass

        entry_idx = None
        for k, entry in sc.items():
            if entry.get("AppName") == name or entry.get("LaunchOptions") == app_id:
                entry_idx = k
                break

        if entry_idx is None:
            num_keys = [int(k) for k in sc.keys() if str(k).isdigit()]
            next_num = max(num_keys) + 1 if num_keys else 0
            entry_idx = str(next_num)

        sc[entry_idx] = {
            "appid": crc,
            "AppName": name,
            "Exe": f'"{launcher_path}"',
            "StartDir": f"{app_dir}/",
            "icon": icon_path if os.path.isfile(icon_path) else "",
            "ShortcutPath": "",
            "LaunchOptions": app_id,
            "IsHidden": 0,
            "AllowDesktopConfig": 1,
            "AllowOverlay": 1,
            "OpenVR": 0,
            "Devkit": 0,
            "DevkitGameID": "",
            "DevkitOverrideAppID": 0,
            "LastPlayTime": 0,
            "FlatpakAppID": "",
            "sortas": "",
            "tags": {"0": "Веб-приложения"},
        }

        try:
            encoded = encode_vdf(root_name, sc)
            with open(shortcuts_file, "wb") as f:
                f.write(encoded)
            added_any = True
        except Exception as e:
            print(f"[WebAppManager] Error saving shortcuts.vdf: {e}", file=sys.stderr)

        localconfig_file = os.path.join(config_dir, "localconfig.vdf")
        if os.path.isfile(localconfig_file):
            try:
                with open(localconfig_file, "r", encoding="utf-8", errors="ignore") as f:
                    lc_content = f.read()
                sc_pos = lc_content.find('"shortcuts"')
                if sc_pos != -1:
                    open_brace = lc_content.find('{', sc_pos)
                    if open_brace != -1 and str(crc) not in lc_content[open_brace:open_brace + 500]:
                        override_snippet = (
                            f'\n\t\t\t\t\t"{crc}"\n\t\t\t\t\t{{\n'
                            f'\t\t\t\t\t\t"ResolutionOverride"\t\t"Native"\n'
                            f'\t\t\t\t\t\t"ResolutionOverrideInternalDisplay"\t\t"1"\n'
                            f'\t\t\t\t\t}}'
                        )
                        lc_content = lc_content[:open_brace + 1] + override_snippet + lc_content[open_brace + 1:]
                        with open(localconfig_file, "w", encoding="utf-8") as f:
                            f.write(lc_content)
            except Exception:
                pass

        _ensure_steam_controller_template(u, name)

    return added_any


def _ensure_steam_controller_template(user_id: str, app_name: str, template: str = "controller_neptune_gamepad+mouse.vdf"):
    """Sets default Steam Input template for a non-Steam shortcut if not already configured."""
    key = re.sub(r'[^a-z0-9 ]+', '', app_name.lower()).strip()
    if not key:
        return
    for root in (
        os.path.join(HOME, ".local", "share", "Steam", "steamapps", "common", "Steam Controller Configs"),
        os.path.join(HOME, ".steam", "steam", "steamapps", "common", "Steam Controller Configs"),
    ):
        cfg_path = os.path.join(root, user_id, "config", "configset_controller_neptune.vdf")
        if not os.path.isfile(cfg_path):
            continue
        try:
            with open(cfg_path, "r", encoding="utf-8", errors="ignore") as f:
                s = f.read()
            if f'"{key}"' in s.lower():
                continue
            idx = s.rfind("}")
            if idx != -1:
                snippet = f'\t"{key}"\n\t{{\n\t\t"template"\t\t"{template}"\n\t}}\n'
                with open(cfg_path, "w", encoding="utf-8") as f:
                    f.write(s[:idx] + snippet + s[idx:])
        except Exception:
            pass


def remove_from_steam(app_id: str) -> bool:
    userdata_root = _find_steam_userdata()
    if not userdata_root:
        return False

    user_dirs = [d for d in os.listdir(userdata_root) if os.path.isdir(os.path.join(userdata_root, d)) and d != "0"]
    removed_any = False
    for u in user_dirs:
        shortcuts_file = os.path.join(userdata_root, u, "config", "shortcuts.vdf")
        if not os.path.isfile(shortcuts_file):
            continue
        try:
            with open(shortcuts_file, "rb") as f:
                root_name, sc = decode_vdf(f.read())
        except Exception:
            continue

        keys_to_remove = []
        for k, entry in sc.items():
            launch_opts = str(entry.get("LaunchOptions", ""))
            exe = str(entry.get("Exe", ""))
            if f'"{app_id}"' in launch_opts or app_id == launch_opts.strip('"') or f"deckybird-webapp-{app_id}" in exe:
                keys_to_remove.append(k)

        if keys_to_remove:
            for k in keys_to_remove:
                del sc[k]
            new_sc = {}
            idx = 0
            for old_k in sorted(sc.keys(), key=lambda x: int(x) if str(x).isdigit() else str(x)):
                new_sc[str(idx)] = sc[old_k]
                idx += 1
            try:
                with open(shortcuts_file, "wb") as f:
                    f.write(encode_vdf(root_name, new_sc))
                removed_any = True
            except Exception:
                pass
    return removed_any


def _get_steam_webapp_ids():
    """Returns a set of webapp IDs currently present in Steam shortcuts.vdf, or None if Steam userdata is unavailable."""
    userdata_root = _find_steam_userdata()
    if not userdata_root:
        return None
    user_dirs = [d for d in os.listdir(userdata_root) if os.path.isdir(os.path.join(userdata_root, d)) and d != "0"]
    if not user_dirs:
        return None

    found_vdf = False
    ids = set()
    for u in user_dirs:
        shortcuts_file = os.path.join(userdata_root, u, "config", "shortcuts.vdf")
        if not os.path.isfile(shortcuts_file):
            continue
        found_vdf = True
        try:
            with open(shortcuts_file, "rb") as f:
                _, sc = decode_vdf(f.read())
            for entry in sc.values():
                exe = str(entry.get("Exe", ""))
                launch_opts = str(entry.get("LaunchOptions", "")).strip().strip('"')
                if "deckybird-webapp-launch" in exe and launch_opts:
                    ids.add(launch_opts)
        except Exception:
            pass
    return ids if found_vdf else None


def list_webapps() -> list:
    results = []
    if not os.path.isdir(WEBAPPS_DIR):
        return results
    steam_ids = _get_steam_webapp_ids()
    for entry in sorted(os.listdir(WEBAPPS_DIR)):
        if steam_ids is not None and entry not in steam_ids:
            continue
        cfg_path = os.path.join(WEBAPPS_DIR, entry, "config.json")
        if os.path.isfile(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                icon_file = os.path.join(WEBAPPS_DIR, entry, "icon.png")
                if os.path.isfile(icon_file):
                    with open(icon_file, "rb") as imgf:
                        cfg["icon_b64"] = "data:image/png;base64," + base64.b64encode(imgf.read()).decode("ascii")
                cfg["has_icon"] = os.path.isfile(icon_file)
                cfg.setdefault("id", entry)
                results.append(cfg)
            except Exception:
                pass
    return results


def delete_webapp(app_id: str) -> dict:
    app_id = sanitize_slug(app_id)
    app_dir = os.path.join(WEBAPPS_DIR, app_id)
    desktop_file = os.path.join(APPLICATIONS_DIR, f"deckybird-webapp-{app_id}.desktop")
    icon_128 = os.path.join(ICONS_DIR, "hicolor", "128x128", "apps", f"deckybird-webapp-{app_id}.png")
    icon_root = os.path.join(ICONS_DIR, f"deckybird-webapp-{app_id}.png")

    remove_from_steam(app_id)
    for path in (desktop_file, icon_128, icon_root):
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
    if os.path.isdir(app_dir):
        try:
            shutil.rmtree(app_dir)
        except Exception:
            pass

    sycoca = shutil.which("kbuildsycoca6") or shutil.which("kbuildsycoca5")
    if sycoca:
        try:
            subprocess.run([sycoca, "--noincremental"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    return {"ok": True, "id": app_id, "message": "Веб-приложение успешно удалено"}


def launch_webapp(app_id: str) -> dict:
    app_id = sanitize_slug(app_id)
    launcher = ensure_launcher_script()
    subprocess.Popen([launcher, app_id], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True, "id": app_id}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="DeckyBird WebApp Manager")
    subparsers = parser.add_subparsers(dest="cmd")

    create_p = subparsers.add_parser("create")
    create_p.add_argument("--name", required=True)
    create_p.add_argument("--url", required=True)
    create_p.add_argument("--icon")
    create_p.add_argument("--no-kde", action="store_true")
    create_p.add_argument("--no-steam", action="store_true")

    subparsers.add_parser("list")
    launch_p = subparsers.add_parser("launch")
    launch_p.add_argument("app_id")
    del_p = subparsers.add_parser("delete")
    del_p.add_argument("app_id")

    args = parser.parse_args()
    if args.cmd == "create":
        icon_b64 = None
        if args.icon and os.path.isfile(args.icon):
            with open(args.icon, "rb") as f:
                icon_b64 = base64.b64encode(f.read()).decode("ascii")
        res = create_webapp(args.name, args.url, icon_b64, not args.no_kde, not args.no_steam)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.cmd == "list":
        print(json.dumps(list_webapps(), indent=2, ensure_ascii=False))
    elif args.cmd == "launch":
        launcher = ensure_launcher_script()
        os.execv(launcher, [launcher, args.app_id])
    elif args.cmd == "delete":
        print(json.dumps(delete_webapp(args.app_id), indent=2, ensure_ascii=False))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
