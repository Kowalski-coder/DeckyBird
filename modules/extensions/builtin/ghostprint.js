// GhostPrint — Anti-Fingerprinting Protection for DeckyBird
(() => {
  if (window.__deckyGhostPrintActive) return;
  window.__deckyGhostPrintActive = true;

  const cfg = Object.assign({
    canvas: true,
    webgl: true,
    audio: true,
    navigator: true,
    webrtc: true
  }, window.__deckyGhostPrintConfig || {});

  // Deterministic per-origin/session seed
  const seedStr = (location.hostname || "deckybird") + "_gp_2026";
  let seed = 0x811c9dc5;
  for (let i = 0; i < seedStr.length; i++) {
    seed ^= seedStr.charCodeAt(i);
    seed = Math.imul(seed, 0x01000193);
  }
  const noise = (idx) => {
    let x = (seed ^ (idx * 2654435761)) >>> 0;
    x ^= x >>> 16;
    return (x & 3) - 1; // -1, 0, 1, 2
  };

  if (cfg.canvas && typeof HTMLCanvasElement !== "undefined") {
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    const origToBlob = HTMLCanvasElement.prototype.toBlob;
    const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;

    const perturbCanvas = (canvas) => {
      try {
        if (canvas.width === 0 || canvas.height === 0 || canvas.width > 512 || canvas.height > 512) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        const img = origGetImageData.call(ctx, 0, 0, 1, 1);
        img.data[0] = (img.data[0] + noise(1)) & 255;
        ctx.putImageData(img, 0, 0);
      } catch (_) {}
    };

    HTMLCanvasElement.prototype.toDataURL = function (...args) {
      perturbCanvas(this);
      return origToDataURL.apply(this, args);
    };
    if (origToBlob) {
      HTMLCanvasElement.prototype.toBlob = function (...args) {
        perturbCanvas(this);
        return origToBlob.apply(this, args);
      };
    }
    CanvasRenderingContext2D.prototype.getImageData = function (sx, sy, sw, sh) {
      const data = origGetImageData.call(this, sx, sy, sw, sh);
      if (data && data.data && data.data.length >= 4 && sw <= 512 && sh <= 512) {
        data.data[0] = (data.data[0] + noise(2)) & 255;
      }
      return data;
    };
  }

  if (cfg.webgl) {
    const patchWebGL = (proto) => {
      if (!proto || !proto.getParameter) return;
      const origGetParam = proto.getParameter;
      proto.getParameter = function (param) {
        // UNMASKED_VENDOR_WEBGL (0x9245), UNMASKED_RENDERER_WEBGL (0x9246)
        if (param === 0x9245) return "Mesa";
        if (param === 0x9246) return "AMD Radeon Graphics (DeckyBird GhostPrint)";
        return origGetParam.apply(this, arguments);
      };
    };
    if (typeof WebGLRenderingContext !== "undefined") patchWebGL(WebGLRenderingContext.prototype);
    if (typeof WebGL2RenderingContext !== "undefined") patchWebGL(WebGL2RenderingContext.prototype);
  }

  if (cfg.audio && typeof AudioBuffer !== "undefined") {
    const origGetChannelData = AudioBuffer.prototype.getChannelData;
    AudioBuffer.prototype.getChannelData = function (channel) {
      const arr = origGetChannelData.call(this, channel);
      if (arr && arr.length > 0 && !arr.__gpPatched) {
        try {
          arr[0] = arr[0] + noise(3) * 1e-7;
          Object.defineProperty(arr, "__gpPatched", { value: true, enumerable: false });
        } catch (_) {}
      }
      return arr;
    };
  }

  if (cfg.navigator) {
    try {
      Object.defineProperty(navigator, "hardwareConcurrency", { get: () => 4, configurable: true });
      Object.defineProperty(navigator, "deviceMemory", { get: () => 8, configurable: true });
    } catch (_) {}
  }

  if (cfg.webrtc && typeof RTCPeerConnection !== "undefined") {
    const OrigRTC = window.RTCPeerConnection;
    window.RTCPeerConnection = function (config, constraints) {
      if (config && Array.isArray(config.iceServers)) {
        config = Object.assign({}, config, { iceTransportPolicy: "relay" });
      }
      return new OrigRTC(config, constraints);
    };
    window.RTCPeerConnection.prototype = OrigRTC.prototype;
  }
})();
