#!/usr/bin/env python3
"""
DeckyBird Extensions Manager & Runtime
- Built-in extensions: VOT, uBlock Origin, Decentraleyes, GhostPrint, Privacy Badger
- Tampermonkey-style Userscripts (.user.js) with auto-updates
"""

import base64
import fnmatch
import hashlib
import json
import os
import re
import shutil
import threading
import time
import urllib.parse
import urllib.request

HOME = os.path.expanduser("~")
DATA_DIR = os.path.join(HOME, ".local", "share", "deckybird")
EXT_DIR = os.path.join(DATA_DIR, "extensions")
CDN_CACHE_DIR = os.path.join(DATA_DIR, "cdn-cache")
STORAGE_DIR = os.path.join(DATA_DIR, "ext-storage")
STATE_FILE = os.path.join(DATA_DIR, "extensions_state.json")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

_STATE_LOCK = threading.Lock()
_PB_SEEN = {}  # third_party_base_domain -> set(first_party_base_domains)

CDN_HOSTS = {
    "ajax.googleapis.com",
    "cdnjs.cloudflare.com",
    "cdn.jsdelivr.net",
    "unpkg.com",
    "code.jquery.com",
    "maxcdn.bootstrapcdn.com",
    "stackpath.bootstrapcdn.com",
    "ajax.aspnetcdn.com",
}

VOT_DOMAINS = (
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be",
    "twitch.tv", "www.twitch.tv", "clips.twitch.tv",
    "vk.com", "m.vk.com", "vkvideo.ru",
    "rutube.ru", "vimeo.com", "player.vimeo.com",
    "tiktok.com", "www.tiktok.com",
    "bilibili.com", "www.bilibili.com",
    "ok.ru", "dzen.ru", "yandex.ru", "ya.ru",
    "coursera.org", "www.coursera.org",
    "udemy.com", "www.udemy.com",
    "ted.com", "www.ted.com",
    "kick.com", "rumble.com", "dailymotion.com",
    "x.com", "twitter.com", "reddit.com", "www.reddit.com",
)

UBLOCK_BLOCKED_DOMAINS = {
    "doubleclick.net", "googlesyndication.com", "googleadservices.com",
    "google-analytics.com", "googletagmanager.com", "adservice.google.com",
    "an.yandex.ru", "mc.yandex.ru", "ads.vk.com", "top-fwz1.mail.ru",
    "adnxs.com", "criteo.com", "outbrain.com", "taboola.com",
    "pubmatic.com", "rubiconproject.com", "openx.net", "casalemedia.com",
    "scorecardresearch.com", "quantserve.com", "amazon-adsystem.com",
    "moatads.com", "adsafeprotected.com", "doubleverify.com",
    "hotjar.com", "mouseflow.com", "fullstory.com", "mixpanel.com",
    "amplitude.com", "segment.io", "segment.com", "sentry.io",
}

KNOWN_TRACKER_DOMAINS = {
    "facebook.net", "connect.facebook.net", "pixel.facebook.com",
    "analytics.twitter.com", "ads-twitter.com", "static.ads-twitter.com",
    "bat.bing.com", "clarity.ms", "analytics.tiktok.com",
    "mc.yandex.ru", "yastatic.net", "vk.com/rtrg",
    "stats.wp.com", "pixel.wp.com", "sb.scorecardresearch.com",
}

UBLOCK_COSMETIC_CSS = """
.ad-banner, .ads-banner, .adsbygoogle, ins.adsbygoogle,
[id^="yandex_rtb_"], [class*="yandex_rtb"],
[id^="ad-"], [class*="ad-banner"], .sponsored-post {
  display: none !important;
}
"""


def _find_builtin_file(filename: str) -> str:
    for candidate in (
        os.path.join(SCRIPT_DIR, "builtin", filename),
        os.path.join(SCRIPT_DIR, "..", "share", "deckybird", "extensions", "builtin", filename),
    ):
        if os.path.isfile(candidate):
            return candidate
    return ""


def _read_builtin_text(filename: str) -> str:
    p = _find_builtin_file(filename)
    if not p:
        return ""
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _default_state() -> dict:
    return {
        "mitm_enabled": True,
        "autoupdate_enabled": True,
        "builtins": {
            "vot": {
                "id": "vot",
                "name": "[VOT] - Voice Over Translation",
                "version": "1.x",
                "description": "Закадровый перевод видео на YouTube, Twitch, VK, Rutube и других сайтах.",
                "enabled": True,
            },
            "ublock": {
                "id": "ublock",
                "name": "uBlock Origin",
                "version": "1.x",
                "description": "Блокировка рекламы, трекеров и косметическая фильтрация элементов.",
                "enabled": True,
                "blocked_count": 0,
                "custom_rules": [],
            },
            "decentraleyes": {
                "id": "decentraleyes",
                "name": "Decentraleyes",
                "version": "2.x",
                "description": "Локальное кэширование и подмена популярных CDN-библиотек без слежки.",
                "enabled": True,
                "hits": 0,
            },
            "ghostprint": {
                "id": "ghostprint",
                "name": "GhostPrint",
                "version": "1.0",
                "description": "Защита от цифрового отпечатка (Canvas, WebGL, AudioContext, Navigator, WebRTC).",
                "enabled": True,
                "config": {
                    "canvas": True,
                    "webgl": True,
                    "audio": True,
                    "navigator": True,
                    "webrtc": True,
                },
            },
            "privacy-badger": {
                "id": "privacy-badger",
                "name": "Privacy Badger",
                "version": "2026.1",
                "description": "Эвристическая защита от сторонних трекеров и скрытого отслеживания cookies.",
                "enabled": True,
                "blocked_count": 0,
                "domains": {},  # domain -> "block" | "cookieblock" | "allow"
            },
        },
        "custom": {},
    }


def load_state() -> dict:
    with _STATE_LOCK:
        if not os.path.isfile(STATE_FILE):
            st = _default_state()
            _save_state_unlocked(st)
            return st
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                st = json.load(f)
        except Exception:
            st = _default_state()
        defaults = _default_state()
        st["mitm_enabled"] = True
        st.setdefault("autoupdate_enabled", True)
        st.setdefault("builtins", {})
        for k, v in defaults["builtins"].items():
            if k not in st["builtins"]:
                st["builtins"][k] = v
        st.setdefault("custom", {})
        return st


def _save_state_unlocked(st: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=2, ensure_ascii=False)
    os.replace(tmp, STATE_FILE)


def save_state(st: dict):
    with _STATE_LOCK:
        _save_state_unlocked(st)


def _base_domain(host: str) -> str:
    host = (host or "").lower().split(":")[0].strip(".")
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def _domain_matches(host: str, domain_set) -> bool:
    host = (host or "").lower().split(":")[0]
    parts = host.split(".")
    for i in range(len(parts)):
        sub = ".".join(parts[i:])
        if sub in domain_set:
            return True
    return False


def should_block_request(host: str, path: str, referer_host: str = "") -> tuple:
    """Returns (blocked: bool, reason: str, strip_cookies: bool)."""
    st = load_state()
    if not st.get("mitm_enabled", True):
        return False, "", False

    host_l = (host or "").lower().split(":")[0]
    if not host_l or host_l in ("127.0.0.1", "localhost"):
        return False, "", False

    # 1. uBlock Origin
    ub = st["builtins"].get("ublock", {})
    if ub.get("enabled", True):
        custom_rules = set(r.strip().lower() for r in ub.get("custom_rules", []) if r.strip())
        if _domain_matches(host_l, UBLOCK_BLOCKED_DOMAINS) or _domain_matches(host_l, custom_rules):
            ub["blocked_count"] = ub.get("blocked_count", 0) + 1
            save_state(st)
            return True, "uBlock Origin", False

    # 2. Privacy Badger
    pb = st["builtins"].get("privacy-badger", {})
    if pb.get("enabled", True) and referer_host:
        ref_base = _base_domain(referer_host)
        req_base = _base_domain(host_l)
        if ref_base and req_base and ref_base != req_base:
            domains_map = pb.setdefault("domains", {})
            action = domains_map.get(req_base)
            if not action and _domain_matches(host_l, KNOWN_TRACKER_DOMAINS):
                action = "cookieblock"
                domains_map[req_base] = action
                save_state(st)
            if action == "block":
                pb["blocked_count"] = pb.get("blocked_count", 0) + 1
                save_state(st)
                return True, "Privacy Badger", False
            if action == "cookieblock":
                return False, "Privacy Badger (cookieblock)", True

    return False, "", False


def record_third_party_cookie(host: str, referer_host: str):
    if not host or not referer_host:
        return
    req_base = _base_domain(host)
    ref_base = _base_domain(referer_host)
    if not req_base or not ref_base or req_base == ref_base:
        return
    seen = _PB_SEEN.setdefault(req_base, set())
    seen.add(ref_base)
    if len(seen) >= 3:
        st = load_state()
        pb = st["builtins"].get("privacy-badger", {})
        if pb.get("enabled", True):
            domains_map = pb.setdefault("domains", {})
            if req_base not in domains_map:
                domains_map[req_base] = "cookieblock"
                save_state(st)


def try_decentraleyes(host: str, path: str):
    """If host is a supported CDN and path is .js/.css, serve from local cache."""
    st = load_state()
    dec = st["builtins"].get("decentraleyes", {})
    if not st.get("mitm_enabled", True) or not dec.get("enabled", True):
        return None
    host_l = (host or "").lower().split(":")[0]
    if host_l not in CDN_HOSTS:
        return None
    clean_path = path.split("?")[0].lower()
    if not (clean_path.endswith(".js") or clean_path.endswith(".css")):
        return None

    os.makedirs(CDN_CACHE_DIR, exist_ok=True)
    key = hashlib.sha256(f"{host_l}{path}".encode("utf-8")).hexdigest()
    cache_path = os.path.join(CDN_CACHE_DIR, key)
    ctype = "application/javascript; charset=utf-8" if clean_path.endswith(".js") else "text/css; charset=utf-8"

    if os.path.isfile(cache_path):
        with open(cache_path, "rb") as f:
            data = f.read()
        dec["hits"] = dec.get("hits", 0) + 1
        save_state(st)
        return data, ctype

    try:
        req = urllib.request.Request(f"https://{host_l}{path}", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                data = resp.read()
                with open(cache_path, "wb") as f:
                    f.write(data)
                dec["hits"] = dec.get("hits", 0) + 1
                save_state(st)
                return data, ctype
    except Exception:
        pass
    return None


def _match_pattern(pattern: str, url: str) -> bool:
    if not pattern:
        return False
    if pattern == "<all_urls>":
        return url.startswith("http://") or url.startswith("https://")
    # Convert Chrome/Userscript match pattern to regex
    if "://" in pattern:
        scheme, rest = pattern.split("://", 1)
        scheme_re = "https?" if scheme == "*" else re.escape(scheme)
        if "/" in rest:
            host_pat, path_pat = rest.split("/", 1)
        else:
            host_pat, path_pat = rest, "*"
        if host_pat == "*":
            host_re = r"[^/]+"
        elif host_pat.startswith("*."):
            host_re = r"(?:[^/]+\.)?" + re.escape(host_pat[2:])
        else:
            host_re = re.escape(host_pat)
        path_re = "/" + re.escape(path_pat).replace(r"\*", ".*")
        regex = f"^{scheme_re}://{host_re}{path_re}$"
        return re.match(regex, url) is not None
    return fnmatch.fnmatch(url, pattern)


def get_injection_snippets(url: str) -> tuple:
    """Returns (head_html, body_html) to inject into HTML responses."""
    st = load_state()
    if not st.get("mitm_enabled", True):
        return "", ""

    head_parts = []
    body_parts = []
    parsed = urllib.parse.urlparse(url)
    host_l = (parsed.hostname or "").lower()

    # 1. GhostPrint (always in <head> before page scripts)
    gp = st["builtins"].get("ghostprint", {})
    if gp.get("enabled", True):
        gp_js = _read_builtin_text("ghostprint.js")
        if gp_js:
            cfg_json = json.dumps(gp.get("config", {}))
            head_parts.append(f"<script>window.__deckyGhostPrintConfig={cfg_json};\n{gp_js}</script>")

    # 2. uBlock Origin cosmetic CSS
    ub = st["builtins"].get("ublock", {})
    if ub.get("enabled", True):
        head_parts.append(f"<style id=\"deckybird-ublock-cosmetic\">{UBLOCK_COSMETIC_CSS}</style>")

    need_polyfill = False
    script_tags_body = []

    # 3. [VOT] Voice Over Translation
    vot = st["builtins"].get("vot", {})
    if vot.get("enabled", True) and any(host_l == d or host_l.endswith("." + d) for d in VOT_DOMAINS):
        vot_js = _read_builtin_text("vot.user.js")
        if vot_js:
            need_polyfill = True
            script_tags_body.append(f"<script id=\"deckybird-vot\">\n{vot_js}\n</script>")

    # 4. Custom installed userscripts / extensions
    for ext_id, ext in st.get("custom", {}).items():
        if not ext.get("enabled", True):
            continue
        ext_root = os.path.join(EXT_DIR, ext_id)
        if ext.get("kind") == "userscript":
            matches = ext.get("matches", [])
            excludes = ext.get("excludes", [])
            if not any(_match_pattern(m, url) for m in matches):
                continue
            if any(_match_pattern(e, url) for e in excludes):
                continue
            us_path = os.path.join(ext_root, ext.get("userscript_file", "script.user.js"))
            if os.path.isfile(us_path):
                with open(us_path, "r", encoding="utf-8", errors="ignore") as f:
                    code = f.read()
                need_polyfill = True
                tag = f"<script data-ext=\"{ext_id}\">\n(() => {{\n{code}\n}})();\n</script>"
                if ext.get("run_at") == "document-start":
                    head_parts.append(tag)
                else:
                    script_tags_body.append(tag)

    if need_polyfill:
        polyfill_js = _read_builtin_text("webext_polyfill.js")
        if polyfill_js:
            head_parts.insert(0, f"<script id=\"deckybird-webext-polyfill\">\n{polyfill_js}\n</script>")

    body_parts.extend(script_tags_body)
    return "\n".join(head_parts), "\n".join(body_parts)


def _parse_userscript_meta(code: str) -> dict:
    name = "Userscript"
    version = "1.0"
    desc = "Пользовательский скрипт"
    author = ""
    update_url = ""
    download_url = ""
    run_at = "document-end"
    matches = []
    excludes = []
    for line in code.splitlines()[:120]:
        m = re.match(r"^\s*//\s*@([a-zA-Z0-9_-]+)\s+(.+)$", line)
        if not m:
            continue
        k, v = m.group(1).lower(), m.group(2).strip()
        if k == "name" and name == "Userscript":
            name = v
        elif k == "version":
            version = v
        elif k == "description" and desc == "Пользовательский скрипт":
            desc = v
        elif k == "author":
            author = v
        elif k == "updateurl":
            update_url = v
        elif k == "downloadurl":
            download_url = v
        elif k == "run-at":
            run_at = v.lower()
        elif k in ("match", "include"):
            matches.append(v)
        elif k == "exclude":
            excludes.append(v)
    if not matches:
        matches = ["<all_urls>"]
    return {
        "name": name,
        "version": version,
        "description": desc,
        "author": author,
        "update_url": update_url,
        "download_url": download_url,
        "run_at": run_at,
        "matches": matches,
        "excludes": excludes,
    }


def _version_tuple(v: str):
    parts = re.findall(r"\d+", str(v or "0"))
    return tuple(int(x) for x in parts) if parts else (0,)


def _is_newer_version(remote_ver: str, local_ver: str) -> bool:
    return _version_tuple(remote_ver) > _version_tuple(local_ver)


def save_userscript_code(code: str, script_id: str = "", source_url: str = "") -> dict:
    if not (code or "").strip():
        return {"ok": False, "error": "Код скрипта не может быть пустым"}
    meta = _parse_userscript_meta(code)
    ext_id = re.sub(r"[^a-zA-Z0-9_-]", "", script_id) if script_id else ""
    if not ext_id:
        ext_id = "us-" + hashlib.sha1(meta["name"].encode("utf-8")).hexdigest()[:10]

    dest = os.path.join(EXT_DIR, ext_id)
    os.makedirs(dest, exist_ok=True)
    with open(os.path.join(dest, "script.user.js"), "w", encoding="utf-8") as f:
        f.write(code)

    st = load_state()
    prev = st.get("custom", {}).get(ext_id, {})
    final_source = source_url or prev.get("source_url", "")
    st["custom"][ext_id] = {
        "id": ext_id,
        "name": meta["name"],
        "version": meta["version"],
        "description": meta["description"],
        "author": meta["author"],
        "source": "userscript",
        "kind": "userscript",
        "enabled": prev.get("enabled", True),
        "matches": meta["matches"],
        "excludes": meta["excludes"],
        "run_at": meta["run_at"],
        "update_url": meta["update_url"] or final_source,
        "download_url": meta["download_url"] or final_source,
        "source_url": final_source,
        "userscript_file": "script.user.js",
        "installed_at": prev.get("installed_at", int(time.time())),
        "updated_at": int(time.time()),
        "last_checked": int(time.time()),
    }
    save_state(st)
    return {"ok": True, "extension": st["custom"][ext_id]}


def install_from_bytes(filename: str, raw_bytes: bytes, source: str = "local", slug: str = "") -> dict:
    fname = (filename or "script.user.js").lower()
    if fname.endswith(".user.js") or fname.endswith(".js"):
        code = raw_bytes.decode("utf-8", errors="ignore")
        return save_userscript_code(code)
    return {"ok": False, "error": "Поддерживаются только пользовательские скрипты (.user.js)"}


def install_from_url(url_or_id: str, slug_hint: str = "") -> dict:
    target = (url_or_id or "").strip()
    if not (target.startswith("http://") or target.startswith("https://")):
        return {"ok": False, "error": "Укажите прямую ссылку (http/https) на .user.js скрипт"}
    req = urllib.request.Request(target, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        raw = resp.read()
    code = raw.decode("utf-8", errors="ignore")
    return save_userscript_code(code, source_url=target)


def check_userscript_updates(script_id: str = "") -> dict:
    st = load_state()
    checked = 0
    updated = []
    errors = []
    now = int(time.time())

    items = list(st.get("custom", {}).items())
    for eid, ext in items:
        if script_id and eid != script_id:
            continue
        if ext.get("kind") != "userscript":
            continue
        check_url = ext.get("update_url") or ext.get("download_url") or ext.get("source_url") or ""
        if not check_url:
            continue
        checked += 1
        try:
            req = urllib.request.Request(check_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                remote_code = resp.read().decode("utf-8", errors="ignore")
            remote_meta = _parse_userscript_meta(remote_code)
            ext["last_checked"] = now
            if _is_newer_version(remote_meta["version"], ext.get("version", "0")):
                dl_url = remote_meta["download_url"] or ext.get("download_url") or check_url
                if dl_url != check_url:
                    req2 = urllib.request.Request(dl_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req2, timeout=20) as resp2:
                        remote_code = resp2.read().decode("utf-8", errors="ignore")
                save_userscript_code(remote_code, script_id=eid, source_url=ext.get("source_url") or dl_url)
                updated.append({"id": eid, "name": remote_meta["name"], "version": remote_meta["version"]})
            else:
                st["custom"][eid]["last_checked"] = now
                save_state(st)
        except Exception as ex:
            errors.append({"id": eid, "error": str(ex)})

    return {"ok": True, "checked": checked, "updated": updated, "errors": errors}


def set_autoupdate(enabled: bool) -> dict:
    st = load_state()
    st["autoupdate_enabled"] = bool(enabled)
    save_state(st)
    return {"ok": True, "autoupdate_enabled": st["autoupdate_enabled"]}


_AUTOUPDATE_STARTED = False


def start_autoupdate_loop():
    global _AUTOUPDATE_STARTED
    if _AUTOUPDATE_STARTED:
        return
    _AUTOUPDATE_STARTED = True

    def _worker():
        time.sleep(20)
        while True:
            try:
                st = load_state()
                if st.get("autoupdate_enabled", True):
                    now = int(time.time())
                    for eid, ext in list(st.get("custom", {}).items()):
                        if ext.get("kind") == "userscript" and (now - ext.get("last_checked", 0)) >= 43200:
                            check_userscript_updates(eid)
            except Exception:
                pass
            time.sleep(3600)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def _load_extension_locales(dest: str, manifest: dict) -> dict:
    locales_dir = os.path.join(dest, "_locales")
    if not os.path.isdir(locales_dir):
        return {}
    candidates = []
    def_loc = manifest.get("default_locale")
    for loc in ("ru", "ru_RU", def_loc, "en", "en_US"):
        if loc and loc not in candidates:
            candidates.append(loc)
    try:
        for d in sorted(os.listdir(locales_dir)):
            if d not in candidates:
                candidates.append(d)
    except Exception:
        pass

    merged = {}
    # Load fallback first, then preferred (ru) on top
    for loc in reversed(candidates):
        msg_file = os.path.join(locales_dir, loc, "messages.json")
        if os.path.isfile(msg_file):
            try:
                with open(msg_file, "r", encoding="utf-8", errors="ignore") as f:
                    raw = json.load(f)
                for k, v in raw.items():
                    if isinstance(v, dict) and "message" in v:
                        merged[k.lower()] = v["message"]
            except Exception:
                pass
    return merged


def _resolve_msg(text: str, messages: dict) -> str:
    if not text or "__MSG_" not in text:
        return text
    def repl(m):
        return messages.get(m.group(1).lower(), m.group(0))
    return re.sub(r"__MSG_([a-zA-Z0-9_@]+)__", repl, text)


def _pick_manifest_icon(manifest: dict, dest: str) -> str:
    icons = manifest.get("icons") or {}
    if not isinstance(icons, dict):
        action = manifest.get("action") or manifest.get("browser_action") or {}
        icons = action.get("default_icon") if isinstance(action.get("default_icon"), dict) else {}
    for size in ("128", "96", "64", "48", "32", "16"):
        rel = icons.get(size)
        if rel and os.path.isfile(os.path.join(dest, rel.lstrip("/"))):
            return rel.lstrip("/")
    for rel in icons.values():
        if isinstance(rel, str) and os.path.isfile(os.path.join(dest, rel.lstrip("/"))):
            return rel.lstrip("/")
    return ""


def _install_zip_extension(ext_id: str, zip_bytes: bytes, source: str, slug: str = "") -> dict:
    dest = os.path.join(EXT_DIR, ext_id)
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        zf.extractall(dest)

    manifest_path = os.path.join(dest, "manifest.json")
    if not os.path.isfile(manifest_path):
        shutil.rmtree(dest, ignore_errors=True)
        return {"ok": False, "error": "В архиве не найден manifest.json"}

    with open(manifest_path, "r", encoding="utf-8", errors="ignore") as f:
        manifest = json.load(f)

    messages = _load_extension_locales(dest, manifest)

    # Extract DNR blocked domains if present
    dnr_domains = []
    dnr = manifest.get("declarative_net_request", {})
    for res in dnr.get("rule_resources", []):
        rp = os.path.join(dest, res.get("path", ""))
        if os.path.isfile(rp):
            try:
                with open(rp, "r", encoding="utf-8", errors="ignore") as rf:
                    rules = json.load(rf)
                for rule in rules[:500]:
                    if rule.get("action", {}).get("type") == "block":
                        cond = rule.get("condition", {})
                        for d in cond.get("requestDomains", []):
                            dnr_domains.append(d.lower())
            except Exception:
                pass

    action = manifest.get("action") or manifest.get("browser_action") or manifest.get("page_action") or {}
    popup_path = (action.get("default_popup") or "").lstrip("/")
    options_path = (manifest.get("options_ui", {}).get("page") or manifest.get("options_page") or "").lstrip("/")
    icon_path = _pick_manifest_icon(manifest, dest)

    name = _resolve_msg(manifest.get("name", ext_id), messages)
    description = _resolve_msg(manifest.get("description", ""), messages)

    st = load_state()
    st["custom"][ext_id] = {
        "id": ext_id,
        "slug": slug or ext_id,
        "name": name,
        "version": manifest.get("version", "1.0"),
        "description": description,
        "source": source,
        "kind": "webext",
        "enabled": True,
        "icon_path": icon_path,
        "popup_path": popup_path,
        "options_path": options_path,
        "content_scripts": manifest.get("content_scripts", []),
        "dnr_domains": dnr_domains,
        "manifest": {
            "name": name,
            "version": manifest.get("version", "1.0"),
            "manifest_version": manifest.get("manifest_version", 2),
        },
        "installed_at": int(time.time()),
    }
    save_state(st)
    return {"ok": True, "extension": st["custom"][ext_id]}


def toggle_extension(ext_id: str, enabled: bool) -> dict:
    st = load_state()
    if ext_id in st["builtins"]:
        st["builtins"][ext_id]["enabled"] = bool(enabled)
    elif ext_id in st["custom"]:
        st["custom"][ext_id]["enabled"] = bool(enabled)
    else:
        return {"ok": False, "error": "Расширение не найдено"}
    save_state(st)
    return {"ok": True, "state": st}


def update_extension_config(ext_id: str, payload: dict) -> dict:
    st = load_state()
    if ext_id == "ublock":
        rules = payload.get("custom_rules")
        if isinstance(rules, list):
            st["builtins"]["ublock"]["custom_rules"] = [str(r).strip() for r in rules if str(r).strip()]
    elif ext_id == "ghostprint":
        cfg = payload.get("config")
        if isinstance(cfg, dict):
            st["builtins"]["ghostprint"]["config"].update(cfg)
    elif ext_id == "privacy-badger":
        domain = payload.get("domain")
        action = payload.get("action")
        if domain and action in ("allow", "block", "cookieblock", "delete"):
            domains = st["builtins"]["privacy-badger"].setdefault("domains", {})
            if action == "delete":
                domains.pop(domain, None)
            else:
                domains[domain] = action
    else:
        return {"ok": False, "error": "Неизвестное расширение"}
    save_state(st)
    return {"ok": True, "state": st}


def remove_custom_extension(ext_id: str) -> dict:
    st = load_state()
    if ext_id not in st.get("custom", {}):
        return {"ok": False, "error": "Расширение не найдено"}
    st["custom"].pop(ext_id, None)
    save_state(st)
    shutil.rmtree(os.path.join(EXT_DIR, ext_id), ignore_errors=True)
    return {"ok": True}


def handle_storage_api(ext_id: str, area: str, body: dict = None) -> dict:
    os.makedirs(STORAGE_DIR, exist_ok=True)
    safe_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", ext_id or "default")
    safe_area = "sync" if area == "sync" else "local"
    p = os.path.join(STORAGE_DIR, f"{safe_id}_{safe_area}.json")
    data = {}
    if os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    if body is not None:
        if body.get("clear"):
            data = {}
        for k in body.get("remove", []):
            data.pop(k, None)
        if isinstance(body.get("set"), dict):
            data.update(body["set"])
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    return {"ok": True, "data": data}


def handle_xhr_proxy(payload: dict) -> dict:
    url = payload.get("url", "")
    method = (payload.get("method") or "GET").upper()
    headers = payload.get("headers") or {}
    data = payload.get("data")
    resp_type = payload.get("responseType", "text")
    try:
        req = urllib.request.Request(
            url,
            data=data.encode("utf-8") if isinstance(data, str) else None,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            hdrs_raw = "\r\n".join(f"{k}: {v}" for k, v in resp.getheaders())
            ctype = resp.headers.get("Content-Type", "")
            out = {
                "ok": True,
                "status": resp.status,
                "statusText": resp.reason or "OK",
                "finalUrl": resp.geturl(),
                "headers_raw": hdrs_raw,
                "content_type": ctype,
            }
            if resp_type in ("arraybuffer", "blob"):
                out["body_b64"] = base64.b64encode(raw).decode("ascii")
            else:
                out["body"] = raw.decode("utf-8", errors="replace")
            return out
    except Exception as ex:
        return {"ok": False, "error": str(ex)}
