/**
 * 學生登入 (server 驗證版)
 *
 * 流程：
 *   1. 先 GET  /api/student/me  看 server 端是否已有 httpOnly cookie
 *   2. 沒有 → 跳 modal → POST /api/student/login → server 種 httpOnly cookie + 寫入 students table
 *   3. localStorage 只存「上次學號」用於預填，不再充當身份來源
 *
 * 重置：點左上角登出 → POST /api/student/logout
 */
(function () {
  "use strict";
  const HINT_KEY = "vtuber.student_hint"; // 只用來預填輸入框
  // device_id 規則必須與後端 _student_auth.DEVICE_ID_PATTERN 一致
  const DEVICE_ID_RE = /^[A-Za-z0-9_\-\u4e00-\u9fff]{1,32}$/;

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function readHint() {
    try { return localStorage.getItem(HINT_KEY) || ""; } catch (_) { return ""; }
  }
  function saveHint(id) {
    try { localStorage.setItem(HINT_KEY, id); } catch (_) {}
  }

  async function fetchMe() {
    try {
      const r = await fetch("/api/student/me", { credentials: "include" });
      if (!r.ok) return null;
      const j = await r.json();
      return j.logged_in ? j.student : null;
    } catch (_) { return null; }
  }

  async function loginRequest(device_id, name) {
    const r = await fetch("/api/student/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ device_id, name }),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || j.error || "登入失敗");
    return j.student;
  }

  async function logoutRequest() {
    try {
      await fetch("/api/student/logout", { method: "POST", credentials: "include" });
    } catch (_) {}
  }

  function showLoginModal(prefill) {
    return new Promise((resolve) => {
      const overlay = document.createElement("div");
      overlay.id = "vtuber-login-overlay";
      overlay.style.cssText = `
        position:fixed; inset:0; z-index:2147483647;
        background:rgba(0,0,0,0.85); display:flex;
        align-items:center; justify-content:center;
        font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      `;
      overlay.innerHTML = `
        <div style="background:#1e1e2e; color:#fff; padding:32px 40px; border-radius:16px; min-width:340px; max-width:90vw; box-shadow:0 20px 60px rgba(0,0,0,0.6);">
          <h2 style="margin:0 0 8px; font-size:22px;">👋 歡迎，請先登入</h2>
          <p style="margin:0 0 16px; color:#aaa; font-size:13px;">輸入你的學號，名字老師會建議使用本名。</p>
          <label style="font-size:12px; color:#888;">學號（必填）</label>
          <input id="vtuber-login-id" type="text" placeholder="例如 s001" autofocus value="${escapeHtml(prefill || "")}"
                 style="width:100%; padding:10px 12px; font-size:16px; border-radius:8px; border:1px solid #444; background:#11111a; color:#fff; box-sizing:border-box; margin-bottom:8px;" />
          <label style="font-size:12px; color:#888;">名字（選填）</label>
          <input id="vtuber-login-name" type="text" placeholder="例如 王小明"
                 style="width:100%; padding:10px 12px; font-size:16px; border-radius:8px; border:1px solid #444; background:#11111a; color:#fff; box-sizing:border-box;" />
          <div id="vtuber-login-err" style="color:#f88; font-size:12px; min-height:16px; margin-top:6px;"></div>
          <div style="display:flex; gap:8px; justify-content:flex-end; margin-top:12px;">
            <button id="vtuber-login-ok"
                    style="padding:8px 20px; background:#4caf50; color:#fff; border:none; border-radius:8px; cursor:pointer; font-size:14px;">進入課堂</button>
          </div>
        </div>`;
      document.body.appendChild(overlay);

      const idInput = overlay.querySelector("#vtuber-login-id");
      const nameInput = overlay.querySelector("#vtuber-login-name");
      const err = overlay.querySelector("#vtuber-login-err");
      const ok = overlay.querySelector("#vtuber-login-ok");

      async function submit() {
        const did = (idInput.value || "").trim();
        const name = (nameInput.value || "").trim();
        if (!did) { err.textContent = "請輸入學號"; return; }
        if (!DEVICE_ID_RE.test(did)) {
          err.textContent = "學號只能用字母 / 數字 / 中文，最多 32 字";
          return;
        }
        ok.disabled = true; ok.textContent = "登入中…";
        try {
          const student = await loginRequest(did, name);
          saveHint(did);
          overlay.remove();
          resolve(student);
        } catch (e) {
          err.textContent = e.message || String(e);
          ok.disabled = false; ok.textContent = "進入課堂";
        }
      }
      ok.addEventListener("click", submit);
      [idInput, nameInput].forEach((el) =>
        el.addEventListener("keydown", (e) => { if (e.key === "Enter") submit(); }));
      setTimeout(() => idInput.focus(), 50);
    });
  }

  function showStudentBadge(student) {
    let badge = document.getElementById("vtuber-student-badge");
    if (badge) badge.remove();
    badge = document.createElement("div");
    badge.id = "vtuber-student-badge";
    badge.style.cssText = `
      position:fixed; top:8px; left:8px; z-index:99998;
      background:rgba(0,0,0,0.55); color:#fff; padding:4px 10px;
      border-radius:14px; font-size:12px; font-family:-apple-system,sans-serif;
      pointer-events:auto; user-select:none;
    `;
    const display = student.name ? `${student.name} (${student.device_id})` : student.device_id;
    badge.innerHTML = `👤 ${escapeHtml(display)} <a href="#" id="vtuber-logout" style="color:#9cf; margin-left:6px; text-decoration:none;">登出</a>`;
    document.body.appendChild(badge);
    badge.querySelector("#vtuber-logout").addEventListener("click", async (e) => {
      e.preventDefault();
      if (!confirm("確定登出？登出後會清掉 attention 校準基線並重新登入。")) return;
      try { localStorage.removeItem("vtuber.attention.baseline"); } catch (_) {}
      await logoutRequest();
      location.reload();
    });
  }

  async function init() {
    let student = await fetchMe();
    if (!student) {
      student = await showLoginModal(readHint());
    }
    window.__VTUBER_STUDENT__ = student;
    showStudentBadge(student);
    document.dispatchEvent(new CustomEvent("vtuber:student-ready", { detail: student }));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.vtuberAuth = {
    me: fetchMe,
    logout: async () => { await logoutRequest(); location.reload(); },
  };
})();
