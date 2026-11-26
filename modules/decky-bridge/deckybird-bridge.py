#!/usr/bin/env python3
"""
DeckyBird Bridge Daemon
1) Local HTTP control & UI server on 127.0.0.1:8406 (Mintsifry, WebApps UI/API, Extensions UI/API).
2) Selective HTTPS/HTTP proxy on 127.0.0.1:8405:
   - Dynamic per-host TLS MITM (signed by local bridge-ca.crt) for Extensions, Userscripts,
     Decentraleyes CDN cache, Privacy Badger, uBlock Origin, GhostPrint, and deckyloader.ru.
"""

import base64
import gzip
import http.client
import json
import mimetypes
import os
import re
import select
import socket
import ssl
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROXY_PORT = 8405
CONTROL_PORT = 8406
TORRENT_PORT = 8404
TARGET_HOSTS = {"deckyloader.ru", "www.deckyloader.ru"}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.expanduser("~"), ".local", "share", "deckybird")
MINCIFRY_FLAG = os.path.join(DATA_DIR, "mincifry_enabled")
BUNDLE_PATH = os.path.join(DATA_DIR, "cacert-bundle.pem")
CA_CERT = os.path.join(DATA_DIR, "bridge-ca.crt")
CA_KEY = os.path.join(DATA_DIR, "bridge-ca.key")
HOST_CERTS_DIR = os.path.join(DATA_DIR, "host-certs")

for _p in (
    os.path.join(SCRIPT_DIR, "..", "webapps"),
    os.path.join(SCRIPT_DIR, "..", "share", "deckybird", "webapps"),
    os.path.join(SCRIPT_DIR, "..", "extensions"),
    os.path.join(SCRIPT_DIR, "..", "share", "deckybird", "extensions"),
):
    _ap = os.path.abspath(_p)
    if os.path.isdir(_ap) and _ap not in sys.path:
        sys.path.insert(0, _ap)

import deckybird_webapp_manager as webapp_mgr
import ext_manager as ext_mgr

BUILTIN_SEARCH_ENGINES = {
    "Bing": "https://www.bing.com/search?q=%s",
    "Brave": "https://search.brave.com/search?q=%s",
    "DuckDuckGo": "https://duckduckgo.com/?q=%s",
    "Ecosia": "https://ecosia.org/search?q=%s",
    "Google": "https://www.google.com/search?q=%s",
    "Kagi": "https://kagi.com/search?q=%s",
    "Mojeek": "https://www.mojeek.com/search?q=%s",
    "Qwant": "https://www.qwant.com/?q=%s&t=web",
    "Startpage": "https://startpage.com/search?q=%s",
    "Yahoo": "https://search.yahoo.com/search?p=%s",
    "Yandex": "https://yandex.com/search/?text=%s",
}


def load_ladybird_settings():
    cfg_root = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    candidates = [
        os.path.join(cfg_root, "Ladybird", "Profiles", "default", "Settings.json"),
        os.path.join(cfg_root, "Ladybird", "Settings.json"),
    ]
    settings_path = next((p for p in candidates if os.path.isfile(p)), "")
    if not settings_path:
        return {}
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_active_search_engine():
    default_name = "DuckDuckGo"
    default_url = BUILTIN_SEARCH_ENGINES[default_name]
    data = load_ladybird_settings()
    se = data.get("searchEngine") or {}
    name = se.get("engine")
    if not name:
        return {"ok": True, "name": default_name, "url": default_url}
    if name in BUILTIN_SEARCH_ENGINES:
        return {"ok": True, "name": name, "url": BUILTIN_SEARCH_ENGINES[name]}
    for custom in se.get("custom") or []:
        if isinstance(custom, dict) and custom.get("name") == name and custom.get("url"):
            return {"ok": True, "name": name, "url": custom["url"]}
    return {"ok": True, "name": default_name, "url": default_url}


def get_appearance_settings():
    data = load_ladybird_settings()
    app = data.get("appearance") or {}
    return {
        "ok": True,
        "interfaceTheme": app.get("interfaceTheme") or "dark",
        "colorTheme": app.get("colorTheme") or "harbor",
    }


def find_certs_dir():
    for candidate in (
        os.environ.get("DECKYBIRD_CERTS_DIR", ""),
        os.path.join(SCRIPT_DIR, "..", "share", "deckybird", "certs"),
        os.path.join(SCRIPT_DIR, "..", "certs"),
    ):
        if candidate and os.path.isdir(candidate):
            return candidate
    return ""


def find_page_script():
    for candidate in (
        os.path.join(SCRIPT_DIR, "decky_page_script.js"),
        os.path.join(SCRIPT_DIR, "..", "share", "deckybird", "decky_page_script.js"),
    ):
        if os.path.isfile(candidate):
            with open(candidate, "r", encoding="utf-8") as f:
                return f.read()
    return ""


def find_ui_file(subpath: str) -> str:
    for base in (
        os.path.join(SCRIPT_DIR, "..", "webapps", "ui"),
        os.path.join(SCRIPT_DIR, "..", "share", "deckybird", "webapps", "ui"),
        os.path.join(SCRIPT_DIR, "..", "extensions", "ui"),
        os.path.join(SCRIPT_DIR, "..", "share", "deckybird", "extensions", "ui"),
    ):
        p = os.path.join(os.path.abspath(base), subpath)
        if os.path.isfile(p):
            return p
    return ""


def is_mincifry_enabled():
    if not os.path.isfile(MINCIFRY_FLAG):
        return True
    try:
        with open(MINCIFRY_FLAG, "r", encoding="utf-8") as f:
            return f.read().strip() != "0"
    except Exception:
        return True


def rebuild_ca_bundle():
    os.makedirs(DATA_DIR, exist_ok=True)
    sys_ca = ""
    for c in ("/etc/ssl/certs/ca-certificates.crt", "/etc/ssl/cert.pem", "/etc/pki/tls/certs/ca-bundle.crt"):
        if os.path.isfile(c):
            sys_ca = c
            break
    if not sys_ca:
        return False

    parts = []
    with open(sys_ca, "r", encoding="utf-8", errors="ignore") as f:
        parts.append(f.read())

    if os.path.isfile(CA_CERT):
        with open(CA_CERT, "r", encoding="utf-8", errors="ignore") as f:
            parts.append("\n" + f.read())

    if is_mincifry_enabled():
        cdir = find_certs_dir()
        if cdir:
            for name in sorted(os.listdir(cdir)):
                if name.endswith(".crt") or name.endswith(".pem"):
                    with open(os.path.join(cdir, name), "r", encoding="utf-8", errors="ignore") as f:
                        parts.append("\n" + f.read())

    tmp_path = BUNDLE_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write("".join(parts))
    os.replace(tmp_path, BUNDLE_PATH)
    return True


def ensure_bridge_certs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(HOST_CERTS_DIR, exist_ok=True)
    if not (os.path.isfile(CA_CERT) and os.path.isfile(CA_KEY)):
        subprocess.run(
            [
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                "-keyout", CA_KEY, "-out", CA_CERT,
                "-days", "3650", "-subj", "/CN=DeckyBird Local Bridge CA",
                "-addext", "basicConstraints=critical,CA:TRUE",
                "-addext", "keyUsage=critical,keyCertSign,cRLSign",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


_CERT_LOCK = threading.Lock()
_SSL_CTX_CACHE = {}


def get_host_ssl_context(host: str) -> ssl.SSLContext:
    host_clean = re.sub(r"[^a-zA-Z0-9._-]", "_", (host or "localhost").lower())
    with _CERT_LOCK:
        if host_clean in _SSL_CTX_CACHE:
            return _SSL_CTX_CACHE[host_clean]

        crt_path = os.path.join(HOST_CERTS_DIR, f"{host_clean}.crt")
        key_path = os.path.join(HOST_CERTS_DIR, f"{host_clean}.key")
        if not (os.path.isfile(crt_path) and os.path.isfile(key_path)):
            csr_path = os.path.join(HOST_CERTS_DIR, f"{host_clean}.csr")
            ext_path = os.path.join(HOST_CERTS_DIR, f"{host_clean}.ext")
            is_ip = bool(re.fullmatch(r"\d+\.\d+\.\d+\.\d+", host or ""))
            san_line = f"subjectAltName=IP:{host}\n" if is_ip else f"subjectAltName=DNS:{host},DNS:*.{host}\n"
            with open(ext_path, "w", encoding="utf-8") as f:
                f.write(
                    "authorityKeyIdentifier=keyid,issuer\n"
                    "basicConstraints=CA:FALSE\n"
                    "keyUsage=digitalSignature,keyEncipherment\n"
                    "extendedKeyUsage=serverAuth\n"
                    + san_line
                )
            subprocess.run(
                [
                    "openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes",
                    "-keyout", key_path, "-out", csr_path,
                    "-subj", f"/CN={host[:60]}",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                [
                    "openssl", "x509", "-req", "-in", csr_path,
                    "-CA", CA_CERT, "-CAkey", CA_KEY, "-CAcreateserial",
                    "-out", crt_path, "-days", "825", "-extfile", ext_path,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for p in (csr_path, ext_path):
                if os.path.exists(p):
                    os.remove(p)

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=crt_path, keyfile=key_path)
        _SSL_CTX_CACHE[host_clean] = ctx
        return ctx


class ControlHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _send_bytes(self, code, ctype, data: bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(204, {})

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/api/mincifry/status":
            self._send_json(200, {"ok": True, "enabled": is_mincifry_enabled()})
        elif path == "/api/search-engine":
            self._send_json(200, get_active_search_engine())
        elif path == "/api/appearance":
            self._send_json(200, get_appearance_settings())
        elif path == "/webapps":
            p = find_ui_file("webapps.html")
            if p:
                with open(p, "rb") as f:
                    self._send_bytes(200, "text/html; charset=utf-8", f.read())
            else:
                self._send_json(404, {"ok": False, "error": "webapps_ui_missing"})
        elif path == "/extensions":
            p = find_ui_file("extensions.html")
            if p:
                with open(p, "rb") as f:
                    self._send_bytes(200, "text/html; charset=utf-8", f.read())
            else:
                self._send_json(404, {"ok": False, "error": "extensions_ui_missing"})
        elif path.startswith("/ext-res/"):
            rel = path[len("/ext-res/"):]
            ext_id, _, inner = rel.partition("/")
            safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", ext_id)
            target = os.path.abspath(os.path.join(ext_mgr.EXT_DIR, safe_id, inner))
            ext_root = os.path.abspath(os.path.join(ext_mgr.EXT_DIR, safe_id))
            if target.startswith(ext_root) and os.path.isfile(target):
                ctype, _ = mimetypes.guess_type(target)
                with open(target, "rb") as f:
                    raw = f.read()
                if (ctype or "").startswith("text/html"):
                    poly = ext_mgr._read_builtin_text("webext_polyfill.js")
                    st = ext_mgr.load_state().get("custom", {}).get(safe_id, {})
                    manifest_json = json.dumps(st.get("manifest", {}))
                    inj = (
                        f"<script>{poly}\n"
                        f"window.chrome=window.__deckyCreateWebExtAPI({json.dumps(safe_id)},{manifest_json});"
                        f"window.browser=window.chrome;</script>"
                    ).encode("utf-8")
                    raw = inj + raw
                self._send_bytes(200, ctype or "application/octet-stream", raw)
            else:
                self._send_json(404, {"ok": False, "error": "not_found"})
        elif path == "/api/webapps/list":
            self._send_json(200, {"ok": True, "items": webapp_mgr.list_webapps()})
        elif path == "/api/webapps/favicon":
            domain = (qs.get("domain") or [""])[0]
            try:
                data = webapp_mgr.fetch_favicon_bytes("https://" + domain)
                if data:
                    self._send_bytes(200, "image/png", data)
                    return
            except Exception:
                pass
            self._send_bytes(404, "text/plain", b"")
        elif path == "/api/ext/state":
            self._send_json(200, ext_mgr.load_state())
        elif path == "/api/ext/storage":
            ext_id = (qs.get("ext") or ["default"])[0]
            area = (qs.get("area") or ["local"])[0]
            self._send_json(200, ext_mgr.handle_storage_api(ext_id, area))
        else:
            self._send_json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/api/mincifry/toggle":
            new_state = not is_mincifry_enabled()
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(MINCIFRY_FLAG, "w", encoding="utf-8") as f:
                f.write("1" if new_state else "0")
            rebuild_ca_bundle()
            self._send_json(200, {"ok": True, "enabled": new_state, "restartRequired": True})
        elif path == "/api/webapps/create":
            body = self._read_json_body()
            res = webapp_mgr.create_webapp(
                name=body.get("name"),
                url=body.get("url"),
                icon_b64=body.get("icon_b64"),
                add_kde=body.get("add_kde", False),
                add_steam=body.get("add_steam", True),
            )
            self._send_json(200, res)
        elif path == "/api/webapps/launch":
            body = self._read_json_body()
            self._send_json(200, webapp_mgr.launch_webapp(body.get("id", "")))
        elif path == "/api/webapps/delete":
            body = self._read_json_body()
            self._send_json(200, webapp_mgr.delete_webapp(body.get("id", "")))
        elif path == "/api/ext/toggle":
            body = self._read_json_body()
            self._send_json(200, ext_mgr.toggle_extension(body.get("id", ""), body.get("enabled", True)))
        elif path == "/api/ext/config":
            body = self._read_json_body()
            self._send_json(200, ext_mgr.update_extension_config(body.get("id", ""), body))
        elif path == "/api/ext/install-url":
            body = self._read_json_body()
            try:
                res = ext_mgr.install_from_url(body.get("url", ""))
            except Exception as ex:
                res = {"ok": False, "error": str(ex)}
            self._send_json(200, res)
        elif path == "/api/ext/install-file":
            body = self._read_json_body()
            try:
                raw = base64.b64decode(body.get("data_b64", ""))
                res = ext_mgr.install_from_bytes(body.get("filename", "ext.zip"), raw, source="local")
            except Exception as ex:
                res = {"ok": False, "error": str(ex)}
            self._send_json(200, res)
        elif path == "/api/ext/remove":
            body = self._read_json_body()
            self._send_json(200, ext_mgr.remove_custom_extension(body.get("id", "")))
        elif path == "/api/ext/storage":
            ext_id = (qs.get("ext") or ["default"])[0]
            area = (qs.get("area") or ["local"])[0]
            self._send_json(200, ext_mgr.handle_storage_api(ext_id, area, self._read_json_body()))
        elif path == "/api/ext/xhr":
            self._send_json(200, ext_mgr.handle_xhr_proxy(self._read_json_body()))
        else:
            self._send_json(404, {"ok": False, "error": "not_found"})


PAGE_SCRIPT_JS = ""


def tunnel_sockets(a, b):
    try:
        while True:
            r, _, _ = select.select([a, b], [], [], 30)
            if not r:
                continue
            for s in r:
                data = s.recv(65536)
                if not data:
                    return
                (b if s is a else a).sendall(data)
    except Exception:
        pass
    finally:
        for s in (a, b):
            try:
                s.close()
            except Exception:
                pass


class SelectiveProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def _handle_plain_http(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length) if length > 0 else None
            parsed = urllib.parse.urlparse(self.path)
            host = parsed.hostname or self.headers.get("Host", "").split(":")[0]
            port = parsed.port or 80
            req_path = parsed.path or "/"
            if parsed.query:
                req_path += "?" + parsed.query

            fwd_headers = {
                k: v for k, v in self.headers.items()
                if k.lower() not in ("host", "proxy-connection", "connection", "content-length", "accept-encoding")
            }
            fwd_headers["Host"] = self.headers.get("Host", host)
            fwd_headers["Accept-Encoding"] = "gzip, deflate"

            conn = http.client.HTTPConnection(host, port, timeout=25)
            conn.request(self.command, req_path, body=body, headers=fwd_headers)
            resp = conn.getresponse()
            resp_body = b"" if self.command == "HEAD" else resp.read()
            resp_headers = [
                (k, v) for k, v in resp.getheaders()
                if k.lower() not in ("transfer-encoding", "content-length", "connection")
            ]
            self._write_http_response(self.wfile, resp.status, resp_headers, resp_body, reason=resp.reason or "OK", is_head=(self.command == "HEAD"))
            conn.close()
        except Exception as ex:
            self.send_error(502, str(ex))

    def do_GET(self):
        self._handle_plain_http()

    def do_POST(self):
        self._handle_plain_http()

    def do_HEAD(self):
        self._handle_plain_http()

    def do_PUT(self):
        self._handle_plain_http()

    def do_DELETE(self):
        self._handle_plain_http()

    def do_OPTIONS(self):
        self._handle_plain_http()

    def do_CONNECT(self):
        host, _, port_str = self.path.partition(":")
        port = int(port_str or "443")

        mitm_active = ext_mgr.load_state().get("mitm_enabled", True)
        if (host.lower() not in TARGET_HOSTS and not mitm_active) or port != 443:
            try:
                remote = socket.create_connection((host, port), timeout=15)
            except Exception as ex:
                self.send_error(502, str(ex))
                return
            self.send_response(200, "Connection Established")
            self.end_headers()
            tunnel_sockets(self.connection, remote)
            return

        self.send_response(200, "Connection Established")
        self.end_headers()
        try:
            ctx = get_host_ssl_context(host)
            tls_conn = ctx.wrap_socket(self.connection, server_side=True)
        except Exception:
            return
        self._handle_tls_http(tls_conn, host)

    def _handle_tls_http(self, tls_conn, host):
        try:
            rfile = tls_conn.makefile("rb")
            wfile = tls_conn.makefile("wb")
            while True:
                req_line = rfile.readline()
                if not req_line:
                    break
                parts = req_line.decode("latin-1").strip().split(" ", 2)
                if len(parts) < 2:
                    break
                method, path = parts[0], parts[1]

                headers = {}
                content_len = 0
                while True:
                    line = rfile.readline()
                    if not line or line in (b"\r\n", b"\n"):
                        break
                    k, _, v = line.decode("latin-1").partition(":")
                    kl = k.strip().lower()
                    headers[kl] = v.strip()
                    if kl == "content-length":
                        content_len = int(v.strip() or "0")

                body = rfile.read(content_len) if content_len > 0 else b""

                # 1. Local deckyloader.ru bridge API
                if host.lower() in TARGET_HOSTS and path.startswith("/__deckybird_api/"):
                    api_sub = path[len("/__deckybird_api/"):]
                    target_url = f"http://127.0.0.1:{TORRENT_PORT}/api/decky/{api_sub}"
                    self._proxy_local_json(wfile, target_url, method, headers, body)
                    continue

                # 2. Local Extensions / Userscripts API (same-origin, zero CORS)
                if path.startswith("/__deckybird_ext_api/"):
                    sub = path[len("/__deckybird_ext_api/"):]
                    target_url = f"http://127.0.0.1:{CONTROL_PORT}/api/ext/{sub}"
                    self._proxy_local_json(wfile, target_url, method, headers, body)
                    continue

                # 3. uBlock Origin / Privacy Badger / DNR blocking
                ref_host = urllib.parse.urlparse(headers.get("referer", "")).hostname or ""
                blocked, reason, strip_cookies = ext_mgr.should_block_request(host, path, ref_host)
                if blocked:
                    self._write_http_response(wfile, 204, {"X-DeckyBird-Blocked": reason}, b"")
                    continue

                # 4. Decentraleyes local CDN cache
                cdn_hit = ext_mgr.try_decentraleyes(host, path)
                if cdn_hit is not None:
                    cdn_bytes, cdn_ctype = cdn_hit
                    self._write_http_response(
                        wfile, 200,
                        {"Content-Type": cdn_ctype, "X-DeckyBird-Decentraleyes": "local-hit"},
                        cdn_bytes,
                    )
                    continue

                # 5. Forward to origin
                fwd_headers = {
                    k: v for k, v in headers.items()
                    if k.lower() not in ("host", "proxy-connection", "connection", "content-length", "accept-encoding")
                }
                if strip_cookies:
                    fwd_headers.pop("cookie", None)
                fwd_headers["Host"] = host
                fwd_headers["Accept-Encoding"] = "gzip, deflate"

                conn = http.client.HTTPSConnection(host, 443, timeout=25)
                conn.request(method, path, body=body if body else None, headers=fwd_headers)
                resp = conn.getresponse()

                resp_headers_list = resp.getheaders()
                for hk, hv in resp_headers_list:
                    if hk.lower() == "set-cookie":
                        ext_mgr.record_third_party_cookie(host, ref_host)

                resp_body = b"" if method == "HEAD" else resp.read()
                resp_headers = [
                    (k, v) for k, v in resp_headers_list
                    if k.lower() not in ("transfer-encoding", "content-length", "connection")
                ]

                ctype = (resp.getheader("Content-Type") or "").lower()
                cenc = (resp.getheader("Content-Encoding") or "").lower()

                if method != "HEAD" and resp.status == 200 and "text/html" in ctype:
                    if cenc == "gzip":
                        try:
                            resp_body = gzip.decompress(resp_body)
                            resp_headers = [(k, v) for k, v in resp_headers if k.lower() != "content-encoding"]
                        except Exception:
                            pass
                    elif cenc == "deflate":
                        try:
                            resp_body = zlib.decompress(resp_body)
                            resp_headers = [(k, v) for k, v in resp_headers if k.lower() != "content-encoding"]
                        except Exception:
                            pass

                    html = resp_body.decode("utf-8", errors="ignore")
                    full_url = f"https://{host}{path}"
                    head_inj, body_inj = ext_mgr.get_injection_snippets(full_url)

                    if host.lower() in TARGET_HOSTS and PAGE_SCRIPT_JS:
                        body_inj += f'\n<script id="deckybird-bridge">\n{PAGE_SCRIPT_JS}\n</script>\n'

                    if head_inj or body_inj:
                        resp_headers = [
                            (k, v) for k, v in resp_headers
                            if k.lower() not in ("content-security-policy", "content-security-policy-report-only")
                        ]
                        if head_inj:
                            h_idx = html.lower().find("<head>")
                            if h_idx != -1:
                                html = html[:h_idx + 6] + "\n" + head_inj + "\n" + html[h_idx + 6:]
                            else:
                                html = head_inj + "\n" + html
                        if body_inj:
                            b_idx = html.lower().rfind("</body>")
                            if b_idx != -1:
                                html = html[:b_idx] + "\n" + body_inj + "\n" + html[b_idx:]
                            else:
                                html += "\n" + body_inj
                        resp_body = html.encode("utf-8")

                self._write_http_response(wfile, resp.status, resp_headers, resp_body, reason=resp.reason or "OK", is_head=(method == "HEAD"))
                conn.close()
        except Exception:
            pass
        finally:
            try:
                tls_conn.close()
            except Exception:
                pass

    def _proxy_local_json(self, wfile, target_url, method, headers, body):
        try:
            req = urllib.request.Request(
                target_url,
                data=body if method in ("POST", "PUT") else None,
                headers={"Content-Type": headers.get("content-type", "application/json")},
                method=method,
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = resp.read()
                status = resp.status
                ctype = resp.headers.get("Content-Type", "application/json")
        except Exception as ex:
            resp_body = json.dumps({"ok": False, "error": str(ex)}).encode("utf-8")
            status = 502
            ctype = "application/json"
        self._write_http_response(wfile, status, {"Content-Type": ctype}, resp_body)

    def _write_http_response(self, wfile, status, headers, body, reason="OK", is_head=False):
        out = [f"HTTP/1.1 {status} {reason}\r\n"]
        items = headers.items() if isinstance(headers, dict) else headers
        for k, v in items:
            out.append(f"{k}: {v}\r\n")
        if status not in (204, 304):
            out.append(f"Content-Length: {len(body)}\r\n")
        out.append("Connection: keep-alive\r\n\r\n")
        wfile.write("".join(out).encode("latin-1") + (b"" if (is_head or status in (204, 304)) else body))
        wfile.flush()


def main():
    ensure_bridge_certs()
    rebuild_ca_bundle()

    if "--init-only" in sys.argv:
        return

    global PAGE_SCRIPT_JS
    PAGE_SCRIPT_JS = find_page_script()

    ctrl_server = ThreadingHTTPServer(("127.0.0.1", CONTROL_PORT), ControlHandler)
    proxy_server = ThreadingHTTPServer(("127.0.0.1", PROXY_PORT), SelectiveProxyHandler)

    t_ctrl = threading.Thread(target=ctrl_server.serve_forever, daemon=True)
    t_ctrl.start()
    proxy_server.serve_forever()


if __name__ == "__main__":
    main()
