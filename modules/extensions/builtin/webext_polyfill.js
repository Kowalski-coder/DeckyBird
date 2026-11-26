// DeckyBird WebExtension & Userscript Runtime Polyfill
(() => {
  if (window.__deckyWebExtRuntimeReady) return;
  window.__deckyWebExtRuntimeReady = true;

  const API_BASE = "/__deckybird_ext_api";

  async function apiCall(path, body) {
    const res = await fetch(API_BASE + path, {
      method: body !== undefined ? "POST" : "GET",
      headers: body !== undefined ? { "Content-Type": "application/json" } : {},
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    return res.json();
  }

  // GM_* / GM.* Userscript API
  window.unsafeWindow = window;

  window.GM_addStyle = function (css) {
    const style = document.createElement("style");
    style.textContent = css;
    (document.head || document.documentElement).appendChild(style);
    return style;
  };

  window.GM_getValue = function (key, defVal) {
    try {
      const raw = localStorage.getItem("__db_gm_" + key);
      return raw !== null ? JSON.parse(raw) : defVal;
    } catch (_) {
      return defVal;
    }
  };

  window.GM_setValue = function (key, val) {
    try {
      localStorage.setItem("__db_gm_" + key, JSON.stringify(val));
    } catch (_) {}
  };

  window.GM_deleteValue = function (key) {
    try {
      localStorage.removeItem("__db_gm_" + key);
    } catch (_) {}
  };

  window.GM_listValues = function () {
    const out = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith("__db_gm_")) out.push(k.slice(8));
    }
    return out;
  };

  window.GM_xmlhttpRequest = function (details) {
    const payload = {
      url: details.url,
      method: details.method || "GET",
      headers: details.headers || {},
      data: typeof details.data === "string" ? details.data : null,
      responseType: details.responseType || "text",
    };

    fetch(API_BASE + "/xhr", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then((r) => r.json())
      .then((res) => {
        if (!res.ok) {
          if (typeof details.onerror === "function") details.onerror(res);
          return;
        }
        let responseObj = res.body || "";
        if (details.responseType === "arraybuffer" && res.body_b64) {
          const bin = atob(res.body_b64);
          const bytes = new Uint8Array(bin.length);
          for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
          responseObj = bytes.buffer;
        } else if (details.responseType === "json") {
          try { responseObj = JSON.parse(res.body || "null"); } catch (_) {}
        } else if (details.responseType === "blob" && res.body_b64) {
          const bin = atob(res.body_b64);
          const bytes = new Uint8Array(bin.length);
          for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
          responseObj = new Blob([bytes], { type: res.content_type || "application/octet-stream" });
        }

        const respArg = {
          status: res.status || 200,
          statusText: res.statusText || "OK",
          finalUrl: res.finalUrl || details.url,
          responseHeaders: res.headers_raw || "",
          responseText: typeof res.body === "string" ? res.body : "",
          response: responseObj,
        };
        if (typeof details.onload === "function") details.onload(respArg);
      })
      .catch((err) => {
        if (typeof details.onerror === "function") details.onerror({ error: String(err) });
      });

    return { abort: () => {} };
  };

  window.GM_info = {
    scriptHandler: "DeckyBird",
    version: "1.0.0",
    script: { name: "DeckyBird Userscript", version: "1.0.0" },
  };

  window.GM = {
    info: window.GM_info,
    addStyle: window.GM_addStyle,
    getValue: async (k, d) => window.GM_getValue(k, d),
    setValue: async (k, v) => window.GM_setValue(k, v),
    deleteValue: async (k) => window.GM_deleteValue(k),
    listValues: async () => window.GM_listValues(),
    xmlHttpRequest: (d) => window.GM_xmlhttpRequest(d),
  };

  // WebExtension chrome.* / browser.* factory per extension
  window.__deckyCreateWebExtAPI = function (extId, manifest) {
    const makeStorageArea = (area) => ({
      get(keys, cb) {
        const p = apiCall(`/storage?ext=${encodeURIComponent(extId)}&area=${area}`).then((r) => {
          const all = r.data || {};
          if (!keys) return all;
          if (typeof keys === "string") return { [keys]: all[keys] };
          if (Array.isArray(keys)) {
            const out = {};
            for (const k of keys) if (k in all) out[k] = all[k];
            return out;
          }
          const out = Object.assign({}, keys);
          for (const k of Object.keys(keys)) if (k in all) out[k] = all[k];
          return out;
        });
        if (typeof cb === "function") p.then(cb);
        return p;
      },
      set(items, cb) {
        const p = apiCall(`/storage?ext=${encodeURIComponent(extId)}&area=${area}`, { set: items || {} });
        if (typeof cb === "function") p.then(() => cb());
        return p;
      },
      remove(keys, cb) {
        const list = Array.isArray(keys) ? keys : [keys];
        const p = apiCall(`/storage?ext=${encodeURIComponent(extId)}&area=${area}`, { remove: list });
        if (typeof cb === "function") p.then(() => cb());
        return p;
      },
      clear(cb) {
        const p = apiCall(`/storage?ext=${encodeURIComponent(extId)}&area=${area}`, { clear: true });
        if (typeof cb === "function") p.then(() => cb());
        return p;
      },
    });

    const api = {
      runtime: {
        id: extId,
        getManifest: () => manifest || {},
        getURL: (path) => `http://127.0.0.1:8406/ext-res/${encodeURIComponent(extId)}/${String(path || "").replace(/^\/+/, "")}`,
        sendMessage: (msg, cb) => {
          const p = Promise.resolve({});
          if (typeof cb === "function") p.then(cb);
          return p;
        },
        onMessage: { addListener: () => {}, removeListener: () => {} },
        onInstalled: { addListener: () => {} },
      },
      storage: {
        local: makeStorageArea("local"),
        sync: makeStorageArea("sync"),
        onChanged: { addListener: () => {}, removeListener: () => {} },
      },
      i18n: {
        getUILanguage: () => navigator.language || "ru",
        getMessage: (key) => key,
      },
    };
    return api;
  };

  if (!window.chrome) window.chrome = window.__deckyCreateWebExtAPI("deckybird-default", {});
  if (!window.browser) window.browser = window.chrome;
})();
