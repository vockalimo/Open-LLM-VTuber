/**
 * 🎭 角色切換漂浮按鈕
 *  - 攔截 OLV 的 WebSocket 實例（main bundle 沒掛在 window 上）
 *  - 開頁時 fetch-configs，在右上角放兩顆按鈕：劇情模式 / 假新聞模式
 *  - 點擊送 switch-config，OLV server 會重啟 agent 並推 set-model 給前端
 */
(() => {
  const TARGETS = [
    { label: "🎭 劇情模式 (雷無桀)", file: "雷無桀.yaml", color: "#7e57c2" },
    { label: "📰 假新聞遊戲", file: "conf.yaml", color: "#26a69a" }, // 主 conf.yaml
  ];

  // ---- 1. 攔截 WebSocket，記住第一個被建立的 instance ----
  const origWS = window.WebSocket;
  let capturedWS = null;
  window.WebSocket = function (url, protocols) {
    const ws = protocols ? new origWS(url, protocols) : new origWS(url);
    if (!capturedWS && /\/client-ws/.test(String(url))) {
      capturedWS = ws;
      window.__olvWS = ws;
      ws.addEventListener("message", (ev) => {
        try {
          const m = JSON.parse(ev.data);
          if (m.type === "config-files") onConfigList(m.configs || []);
          if (m.type === "config-switched" || m.type === "set-model-and-conf")
            onSwitched(m);
          if (m.type === "set-background" && m.url) {
            // OLV 主 bundle 不認識此 type，由 overlay 直接設定背景圖 src
            const bgImg = document.querySelector('img[alt="background"]');
            if (bgImg) bgImg.src = m.url;
          }
        } catch (_) {}
      });
      ws.addEventListener("open", () => {
        // 連上後問一次有哪些角色（純為了驗證 alias 對得上）
        try { ws.send(JSON.stringify({ type: "fetch-configs" })); } catch (_) {}
      });
    }
    return ws;
  };
  window.WebSocket.prototype = origWS.prototype;
  for (const k in origWS) {
    try { window.WebSocket[k] = origWS[k]; } catch (_) {}
  }

  // ---- 2. UI ----
  function build() {
    if (document.getElementById("char-switch-bar")) return;
    const bar = document.createElement("div");
    bar.id = "char-switch-bar";
    bar.style.cssText =
      "position:fixed;top:8px;left:50%;transform:translateX(-50%);" +
      "display:flex;gap:8px;z-index:99999;font:13px/1 -apple-system,sans-serif;";
    for (const t of TARGETS) {
      const b = document.createElement("button");
      b.textContent = t.label;
      b.dataset.file = t.file;
      b.style.cssText =
        `background:${t.color};color:#fff;border:0;border-radius:18px;` +
        "padding:8px 14px;cursor:pointer;box-shadow:0 2px 6px rgba(0,0,0,.3);" +
        "opacity:0.85;transition:opacity .2s, transform .1s;";
      b.onmouseenter = () => (b.style.opacity = "1");
      b.onmouseleave = () => (b.style.opacity = "0.85");
      b.onclick = () => doSwitch(t.file, b);
      bar.appendChild(b);
    }
    const status = document.createElement("span");
    status.id = "char-switch-status";
    status.style.cssText =
      "background:rgba(0,0,0,.6);color:#fff;padding:6px 10px;border-radius:14px;align-self:center;";
    bar.appendChild(status);
    document.body.appendChild(bar);
  }

  function setStatus(msg) {
    const el = document.getElementById("char-switch-status");
    if (el) el.textContent = msg;
  }

  function doSwitch(file, btn) {
    if (!capturedWS || capturedWS.readyState !== 1) {
      setStatus("WS 還沒連上，等一下…");
      return;
    }
    btn.style.transform = "scale(0.95)";
    setTimeout(() => (btn.style.transform = ""), 150);
    capturedWS.send(JSON.stringify({ type: "switch-config", file }));
    setStatus(`切換中：${file}`);
  }

  function onConfigList(list) {
    const names = list.map((c) => c.filename || c.name || JSON.stringify(c));
    console.log("[char-switch] 可用角色：", names);
  }

  function onSwitched(_m) {
    setStatus("✅ 已切換");
    setTimeout(() => setStatus(""), 2500);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", build);
  } else {
    build();
  }
})();
