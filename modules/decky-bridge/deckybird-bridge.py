#!/usr/bin/env python3
"""
DeckyBird Bridge Daemon
1) Local HTTP control API on 127.0.0.1:8406 (Mintsifry certs toggle).
2) Selective HTTPS proxy on 127.0.0.1:8405:
   - Transparent TCP tunnel for all domains except deckyloader.ru.
   - For deckyloader.ru: injects decky_page_script.js and proxies /__deckybird_api/* to 127.0.0.1:8404/api/decky/*.
"""

import http.client
import json
import os
import select
import socket
import ssl
import subprocess
import sys
import threading
import urllib.request
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
SITE_CERT = os.path.join(DATA_DIR, "bridge-site.crt")
SITE_KEY = os.path.join(DATA_DIR, "bridge-site.key")

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

    if not (os.path.isfile(SITE_CERT) and os.path.isfile(SITE_KEY)):
        csr_path = os.path.join(DATA_DIR, "bridge-site.csr")
        ext_path = os.path.join(DATA_DIR, "bridge-site.ext")
        with open(ext_path, "w", encoding="utf-8") as f:
            f.write(
                "authorityKeyIdentifier=keyid,issuer\n"
                "basicConstraints=CA:FALSE\n"
                "keyUsage=digitalSignature,keyEncipherment\n"
                "extendedKeyUsage=serverAuth\n"
                "subjectAltName=DNS:deckyloader.ru,DNS:www.deckyloader.ru\n"
            )
        subprocess.run(
            [
                "openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes",
                "-keyout", SITE_KEY, "-out", csr_path,
                "-subj", "/CN=deckyloader.ru",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                "openssl", "x509", "-req", "-in", csr_path,
                "-CA", CA_CERT, "-CAkey", CA_KEY, "-CAcreateserial",
                "-out", SITE_CERT, "-days", "825", "-extfile", ext_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for p in (csr_path, ext_path):
            if os.path.exists(p):
                os.remove(p)


class ControlHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(204, {})

    def do_GET(self):
        if self.path == "/api/mincifry/status":
            self._send_json(200, {"ok": True, "enabled": is_mincifry_enabled()})
        elif self.path == "/api/search-engine":
            self._send_json(200, get_active_search_engine())
        elif self.path == "/api/appearance":
            self._send_json(200, get_appearance_settings())
        else:
            self._send_json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        if self.path == "/api/mincifry/toggle":
            new_state = not is_mincifry_enabled()
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(MINCIFRY_FLAG, "w", encoding="utf-8") as f:
                f.write("1" if new_state else "0")
            rebuild_ca_bundle()
            self._send_json(200, {"ok": True, "enabled": new_state, "restartRequired": True})
        else:
            self._send_json(404, {"ok": False, "error": "not_found"})


PAGE_SCRIPT_JS = ""
SSL_CTX = None


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

    def do_CONNECT(self):
        host, _, port_str = self.path.partition(":")
        port = int(port_str or "443")

        if host.lower() not in TARGET_HOSTS or port != 443:
            try:
                remote = socket.create_connection((host, port), timeout=15)
            except Exception as ex:
                self.send_error(502, str(ex))
                return
            self.send_response(200, "Connection Established")
            self.end_headers()
            tunnel_sockets(self.connection, remote)
            return

        # Intercept deckyloader.ru
        self.send_response(200, "Connection Established")
        self.end_headers()
        try:
            tls_conn = SSL_CTX.wrap_socket(self.connection, server_side=True)
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

                # Local bridge API proxy -> 127.0.0.1:8404/api/decky/...
                if path.startswith("/__deckybird_api/"):
                    api_sub = path[len("/__deckybird_api/"):]
                    target_url = f"http://127.0.0.1:{TORRENT_PORT}/api/decky/{api_sub}"
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
                    continue

                # Forward to real deckyloader.ru
                fwd_headers = {
                    k: v for k, v in headers.items()
                    if k not in ("host", "proxy-connection", "connection", "accept-encoding", "content-length")
                }
                fwd_headers["Host"] = host
                fwd_headers["Accept-Encoding"] = "identity"

                conn = http.client.HTTPSConnection(host, 443, timeout=20)
                conn.request(method, path, body=body if body else None, headers=fwd_headers)
                resp = conn.getresponse()
                resp_body = resp.read()
                resp_headers = {k: v for k, v in resp.getheaders() if k.lower() not in ("transfer-encoding", "content-length", "connection")}

                ctype = resp.getheader("Content-Type", "")
                if "text/html" in ctype.lower() and PAGE_SCRIPT_JS:
                    html = resp_body.decode("utf-8", errors="ignore")
                    inject_tag = f"\n<script id=\"deckybird-bridge\">\n{PAGE_SCRIPT_JS}\n</script>\n"
                    idx = html.lower().rfind("</body>")
                    if idx != -1:
                        html = html[:idx] + inject_tag + html[idx:]
                    else:
                        html += inject_tag
                    resp_body = html.encode("utf-8")

                self._write_http_response(wfile, resp.status, resp_headers, resp_body)
                conn.close()
        except Exception:
            pass
        finally:
            try:
                tls_conn.close()
            except Exception:
                pass

    def _write_http_response(self, wfile, status, headers, body):
        out = [f"HTTP/1.1 {status} OK\r\n"]
        for k, v in headers.items():
            out.append(f"{k}: {v}\r\n")
        out.append(f"Content-Length: {len(body)}\r\n")
        out.append("Connection: keep-alive\r\n\r\n")
        wfile.write("".join(out).encode("latin-1") + body)
        wfile.flush()


def main():
    global PAGE_SCRIPT_JS, SSL_CTX
    ensure_bridge_certs()
    rebuild_ca_bundle()

    if "--init-only" in sys.argv:
        return

    PAGE_SCRIPT_JS = find_page_script()
    SSL_CTX = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    SSL_CTX.load_cert_chain(certfile=SITE_CERT, keyfile=SITE_KEY)

    ctrl_server = ThreadingHTTPServer(("127.0.0.1", CONTROL_PORT), ControlHandler)
    proxy_server = ThreadingHTTPServer(("127.0.0.1", PROXY_PORT), SelectiveProxyHandler)

    t_ctrl = threading.Thread(target=ctrl_server.serve_forever, daemon=True)
    t_ctrl.start()
    proxy_server.serve_forever()


if __name__ == "__main__":
    main()
