/**
 * 👀 簡易專心度偵測（webcam → MediaPipe FaceLandmarker → focus/bored/confused）
 *
 * 設計目標：
 *  - 不動 OLV 已 build 的 main bundle，獨立掛在 index.html 末尾
 *  - 預設關閉，需要在 console 執行 window.attentionTracker.start()
 *    或在 URL 加 `?attention=1` 自動啟動
 *  - 每秒推 1 筆 engagement event 到 server `/api/attention/engagement`
 *  - 完全失敗時靜默退出，不影響 OLV 主流程
 *
 * 三個分數啟發式（粗略，先有訊號為主）：
 *   focus    = 臉正對 + 眼睛睜開 + 在畫面中央
 *   bored    = 視線飄移 / 頭低 / 眨眼頻率高
 *   confused = 皺眉（眉間距變窄）+ 眼睛瞇
 */
(() => {
  const POST_INTERVAL_MS = 1000;       // 1 秒推一筆
  const INFER_INTERVAL_MS = 200;       // 5 fps 推論
  const ENDPOINT = "/api/attention/engagement";

  const params = new URLSearchParams(location.search);
  const AUTOSTART = params.get("attention") === "1";
  const DEBUG_DEFAULT = params.get("debug") === "1";

  // 計算 EAR (Eye Aspect Ratio)：垂直距離 / 水平距離
  // FaceLandmarker 468 點：左眼 33,160,158,133,153,144；右眼 362,385,387,263,373,380
  const LEFT_EYE = [33, 160, 158, 133, 153, 144];
  const RIGHT_EYE = [362, 385, 387, 263, 373, 380];
  // 眉毛內側、眉毛外側（用來偵測皺眉）
  const LEFT_BROW_INNER = 55;
  const RIGHT_BROW_INNER = 285;

  function dist(a, b) {
    const dx = a.x - b.x, dy = a.y - b.y;
    return Math.hypot(dx, dy);
  }

  function ear(lm, eye) {
    const v = (dist(lm[eye[1]], lm[eye[5]]) + dist(lm[eye[2]], lm[eye[4]])) / 2;
    const h = dist(lm[eye[0]], lm[eye[3]]);
    return h > 0 ? v / h : 0;
  }

  function clamp01(x) { return Math.max(0, Math.min(1, x)); }

  class AttentionTracker {
    constructor() {
      this.video = null;
      this.landmarker = null;
      this.running = false;
      this.lastInferTs = 0;
      this.lastPostTs = 0;
      this.recent = [];          // 最近 N 筆樣本，用來做平滑
      this.blinkBuf = [];        // 最近 10 秒的眨眼時間戳
      this.lastEarSum = 1;
      this._raf = null;
      // 個人化基線：前 30 秒收集，之後用來修正分數
      this.startTs = 0;
      this.calibrating = true;
      this.calibBuf = [];        // {focus, bored, confused}
      this.baseline = null;      // {focus_mean, focus_std, bored_mean, confused_mean}
      this.CALIB_DURATION_MS = 30000;
      this.debug = DEBUG_DEFAULT;
      this.debugCanvas = null;
      this.debugCtx = null;
      this.debugInfo = null;
      this.lastScores = { focus: 0, bored: 0, confused: 0, label: "-" };
      // 允許外部帶入已存的 baseline（localStorage）
      try {
        const saved = localStorage.getItem("vtuber.attention.baseline");
        if (saved) {
          this.baseline = JSON.parse(saved);
          this.calibrating = false;
          console.log("[attention] loaded baseline from localStorage", this.baseline);
        }
      } catch (_) {}
    }

    async start() {
      if (this.running) {
        console.warn("[attention] already running");
        return;
      }
      try {
        // 動態載入 MediaPipe Tasks Vision (CDN)
        const vision = await import(
          "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/vision_bundle.mjs"
        );
        const { FaceLandmarker, FilesetResolver } = vision;

        const fileset = await FilesetResolver.forVisionTasks(
          "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm"
        );
        this.landmarker = await FaceLandmarker.createFromOptions(fileset, {
          baseOptions: {
            modelAssetPath:
              "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
            delegate: "GPU",
          },
          outputFaceBlendshapes: true,
          outputFacialTransformationMatrixes: true,
          runningMode: "VIDEO",
          numFaces: 1,
        });

        // webcam
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 320, height: 240, facingMode: "user" },
          audio: false,
        });
        this.video = document.createElement("video");
        this.video.srcObject = stream;
        this.video.autoplay = true;
        this.video.playsInline = true;
        this.video.muted = true;
        this.video.style.cssText =
          "position:fixed;bottom:8px;right:8px;width:120px;height:90px;border:2px solid #4caf50;border-radius:6px;z-index:99999;opacity:0.7;";
        document.body.appendChild(this.video);
        await new Promise((r) => this.video.addEventListener("loadeddata", r, { once: true }));

        if (this.debug) this._buildDebugUI();

        // 校準進度條 overlay (疊在 webcam 預覽上方)
        if (!this.baseline) {
          this._buildCalibUI();
        }

        this.running = true;
        this.startTs = performance.now();
        this._loop();
        console.log(this.baseline ? "[attention] ✅ tracker started (baseline 已載入)" : "[attention] ✅ tracker started, 校準中… 請保持自然狀態 30 秒");
      } catch (e) {
        if (e.name === "NotFoundError" || e.name === "DevicesNotFoundError") {
          console.log("[attention] 沒有攝影機，attention tracker 停用。");
        } else {
          console.warn("[attention] start failed:", e);
        }
        this.stop();
      }
    }

    _buildCalibUI() {
      const wrap = document.createElement("div");
      wrap.id = "attention-calib-ui";
      wrap.style.cssText =
        "position:fixed;bottom:104px;right:8px;width:200px;background:rgba(0,0,0,0.78);" +
        "color:#fff;padding:8px 10px;border-radius:8px;z-index:99999;" +
        "font:12px/1.4 -apple-system,sans-serif;pointer-events:none;";
      wrap.innerHTML =
        '<div style="margin-bottom:4px;">🎯 <b>專注度校準中</b>，請保持自然狀態</div>' +
        '<div id="attention-calib-bar-bg" style="height:6px;background:#333;border-radius:3px;overflow:hidden;">' +
        '<div id="attention-calib-bar" style="height:100%;width:0%;background:linear-gradient(90deg,#4caf50,#8bc34a);transition:width .3s;"></div>' +
        '</div>' +
        '<div id="attention-calib-pct" style="text-align:right;margin-top:2px;color:#aaa;">0%</div>';
      document.body.appendChild(wrap);
      // 把 webcam 邊框改成黃色提示「校準中」
      if (this.video) this.video.style.borderColor = "#ffb74d";
    }

    _updateCalibUI(elapsedMs) {
      const bar = document.getElementById("attention-calib-bar");
      const pct = document.getElementById("attention-calib-pct");
      if (!bar || !pct) return;
      const ratio = Math.min(1, elapsedMs / this.CALIB_DURATION_MS);
      const p = Math.round(ratio * 100);
      bar.style.width = p + "%";
      pct.textContent = p + "%";
    }

    _removeCalibUI(success) {
      const wrap = document.getElementById("attention-calib-ui");
      if (wrap) {
        if (success) {
          wrap.innerHTML = '<div style="color:#8bc34a">✅ 校準完成，已建立你的專注基線</div>';
          setTimeout(() => wrap.remove(), 2500);
        } else {
          wrap.innerHTML = '<div style="color:#ff9800">⚠️ 校準樣本不足，使用預設分數</div>';
          setTimeout(() => wrap.remove(), 2500);
        }
      }
      if (this.video) this.video.style.borderColor = "#4caf50";
    }

    stop() {
      this.running = false;
      if (this._raf) cancelAnimationFrame(this._raf);
      if (this.video?.srcObject) {
        for (const t of this.video.srcObject.getTracks()) t.stop();
      }
      if (this.video) this.video.remove();
      this.video = null;
      this._removeDebugUI();
      console.log("[attention] stopped");
    }

    setDebug(on) {
      this.debug = !!on;
      if (this.debug) {
        if (this.video) this._buildDebugUI();
      } else {
        this._removeDebugUI();
      }
      console.log("[attention] debug =", this.debug);
    }

    _buildDebugUI() {
      if (this.debugCanvas || !this.video) return;
      const v = this.video;
      // 把預覽放大一點，比較看得到框
      v.style.width = "240px";
      v.style.height = "180px";
      const c = document.createElement("canvas");
      c.width = 240;
      c.height = 180;
      c.style.cssText =
        "position:fixed;bottom:8px;right:8px;width:240px;height:180px;" +
        "pointer-events:none;z-index:99999;border-radius:6px;";
      document.body.appendChild(c);
      this.debugCanvas = c;
      this.debugCtx = c.getContext("2d");

      const info = document.createElement("div");
      info.style.cssText =
        "position:fixed;bottom:192px;right:8px;width:240px;background:rgba(0,0,0,0.78);" +
        "color:#fff;padding:6px 8px;border-radius:6px;z-index:99999;" +
        "font:11px/1.4 ui-monospace,Menlo,monospace;pointer-events:none;";
      document.body.appendChild(info);
      this.debugInfo = info;
    }

    _removeDebugUI() {
      if (this.debugCanvas) { this.debugCanvas.remove(); this.debugCanvas = null; this.debugCtx = null; }
      if (this.debugInfo) { this.debugInfo.remove(); this.debugInfo = null; }
      if (this.video) { this.video.style.width = "120px"; this.video.style.height = "90px"; }
    }

    _drawDebug(lm) {
      const ctx = this.debugCtx;
      if (!ctx) return;
      const W = this.debugCanvas.width, H = this.debugCanvas.height;
      ctx.clearRect(0, 0, W, H);
      // webcam 是鏡像顯示（但 landmark x 是相對原始畫面），畫框時要鏡像 X
      const px = (p) => ({ x: (1 - p.x) * W, y: p.y * H });
      const polyline = (idxs, color, close = true) => {
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        idxs.forEach((i, k) => {
          const p = px(lm[i]);
          if (k === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y);
        });
        if (close) ctx.closePath();
        ctx.stroke();
      };
      // 雙眼（綠）
      polyline(LEFT_EYE, "#00e676");
      polyline(RIGHT_EYE, "#00e676");
      // 眉內側兩點連線（黃）
      ctx.strokeStyle = "#ffeb3b";
      ctx.lineWidth = 2;
      ctx.beginPath();
      const bl = px(lm[LEFT_BROW_INNER]), br = px(lm[RIGHT_BROW_INNER]);
      ctx.moveTo(bl.x, bl.y); ctx.lineTo(br.x, br.y); ctx.stroke();
      // 鼻尖（紅）
      const nose = px(lm[1]);
      ctx.fillStyle = "#f44336";
      ctx.beginPath(); ctx.arc(nose.x, nose.y, 4, 0, Math.PI * 2); ctx.fill();
      // 中線
      ctx.strokeStyle = "rgba(255,255,255,0.25)";
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(W / 2, 0); ctx.lineTo(W / 2, H); ctx.stroke();

      if (this.debugInfo) {
        const s = this.lastScores;
        const bar = (v) => "█".repeat(Math.round(v * 10)).padEnd(10, "░");
        this.debugInfo.innerHTML =
          `<div>label: <b style="color:#8bc34a">${s.label}</b></div>` +
          `<div>focus    ${bar(s.focus)} ${s.focus.toFixed(2)}</div>` +
          `<div>bored    ${bar(s.bored)} ${s.bored.toFixed(2)}</div>` +
          `<div>confused ${bar(s.confused)} ${s.confused.toFixed(2)}</div>`;
      }
    }

    _loop = () => {
      if (!this.running) return;
      const now = performance.now();
      if (now - this.lastInferTs >= INFER_INTERVAL_MS && this.video?.readyState >= 2) {
        this.lastInferTs = now;
        try {
          const result = this.landmarker.detectForVideo(this.video, now);
          if (result?.faceLandmarks?.length) {
            const blend = result.faceBlendshapes?.[0]?.categories || null;
            const matrix = result.facialTransformationMatrixes?.[0]?.data || null;
            this._onFace(result.faceLandmarks[0], now, blend, matrix);
            if (this.debug) this._drawDebug(result.faceLandmarks[0]);
          } else {
            // 沒偵測到臉 → 標 absent，三維皆 0（不污染 bored 平均）
            this._pushSample({ focus: 0, bored: 0, confused: 0, absent: true, raw: { face: false } });
            this.lastScores = { focus: 0, bored: 0, confused: 0, label: "absent" };
            if (this.debug && this.debugCtx) {
              this.debugCtx.clearRect(0, 0, this.debugCanvas.width, this.debugCanvas.height);
              if (this.debugInfo) {
                this.debugInfo.innerHTML =
                  '<div>label: <b style="color:#ff5252">absent</b> (鏡頭沒看到臉)</div>';
              }
            }
          }
        } catch (e) {
          // 推論失敗忽略
        }
      }
      if (now - this.lastPostTs >= POST_INTERVAL_MS) {
        this.lastPostTs = now;
        this._postAggregate();
      }
      this._raf = requestAnimationFrame(this._loop);
    };

    _onFace(lm, now, blend, matrix) {
      const earL = ear(lm, LEFT_EYE);
      const earR = ear(lm, RIGHT_EYE);
      const earSum = (earL + earR) / 2;

      // 偵測眨眼（EAR 從高跌到低再回來）
      if (this.lastEarSum > 0.22 && earSum < 0.18) {
        this.blinkBuf.push(now);
      }
      this.lastEarSum = earSum;
      // 只保留 10 秒內的眨眼
      const cutoff = now - 10000;
      while (this.blinkBuf.length && this.blinkBuf[0] < cutoff) this.blinkBuf.shift();

      // 頭部姿態粗估：用鼻尖(1) 與兩眼中心連線判斷 yaw
      const noseTip = lm[1];
      const leftEyeCenter = lm[33];
      const rightEyeCenter = lm[263];
      const eyeMidX = (leftEyeCenter.x + rightEyeCenter.x) / 2;
      const yaw = Math.abs(noseTip.x - eyeMidX) / Math.max(0.001, dist(leftEyeCenter, rightEyeCenter));

      // 鼻尖在畫面中心程度
      const centerness = 1 - Math.min(1, Math.abs(noseTip.x - 0.5) * 2);

      // 眨眼頻率（次/分鐘）
      const blinkRate = (this.blinkBuf.length / 10) * 60;

      // ===== 用 blendshapes 取代手算特徵 =====
      const bs = {};
      if (blend) for (const c of blend) bs[c.categoryName] = c.score;
      const get = (k) => bs[k] || 0;

      // 表情訊號（0~1）
      const browDown   = (get("browDownLeft") + get("browDownRight")) / 2;       // 皺眉外側
      const browInnerUp = (get("browInnerUp")) ;                                 // 揚眉（驚訝/疑問）
      const browOuterUp = (get("browOuterUpLeft") + get("browOuterUpRight")) / 2;
      const eyeBlink   = (get("eyeBlinkLeft") + get("eyeBlinkRight")) / 2;       // 0=睜 1=閉
      const eyeSquint  = (get("eyeSquintLeft") + get("eyeSquintRight")) / 2;     // 瞇眼
      const eyeLookDown = (get("eyeLookDownLeft") + get("eyeLookDownRight")) / 2;
      const eyeLookOutL = get("eyeLookOutLeft");
      const eyeLookOutR = get("eyeLookOutRight");
      const eyeLookSide = Math.max(eyeLookOutL, eyeLookOutR);
      const mouthSmile = (get("mouthSmileLeft") + get("mouthSmileRight")) / 2;
      const mouthFrown = (get("mouthFrownLeft") + get("mouthFrownRight")) / 2;
      const jawOpen    = get("jawOpen");                                         // 打哈欠
      const eyeOpen    = clamp01(1 - eyeBlink);

      const frown = clamp01(browDown * 1.5);                                     // 皺眉
      const surprise = clamp01(browInnerUp * 0.7 + browOuterUp * 0.3);           // 驚訝/疑問

      // ===== 重新合成三維 =====
      const focusRaw = clamp01(
        0.35 * (1 - Math.min(1, yaw * 3)) +    // 臉正對
        0.25 * centerness +                     // 在畫面中央
        0.25 * eyeOpen +                        // 眼睛睜開
        0.15 * (1 - eyeLookDown) * (1 - eyeLookSide)  // 視線正視前方
      );
      const boredRaw = clamp01(
        0.35 * eyeBlink +                       // 眼睛半閉
        0.25 * eyeLookDown +                    // 看下面
        0.20 * Math.min(1, blinkRate / 30) +    // 高眨眼頻率
        0.20 * jawOpen                          // 打哈欠
      );
      const confusedRaw = clamp01(
        0.45 * frown +                          // 皺眉
        0.30 * surprise +                       // 揚眉（疑問）
        0.15 * eyeSquint +                      // 瞇眼盯
        0.10 * mouthFrown                       // 嘴角下拉
      );

      // 互斥化
      const suppress = 1 - focusRaw;
      const bored = +(boredRaw * suppress).toFixed(3);
      const confused = +(confusedRaw * suppress).toFixed(3);
      const focus = +focusRaw.toFixed(3);

      this._pushSample({
        focus, bored, confused,
        raw: {
          ear: +earSum.toFixed(3), yaw: +yaw.toFixed(3),
          blinkRate: +blinkRate.toFixed(1), centerness: +centerness.toFixed(3),
          browDown: +browDown.toFixed(3), browInnerUp: +browInnerUp.toFixed(3),
          eyeBlink: +eyeBlink.toFixed(3), eyeSquint: +eyeSquint.toFixed(3),
          eyeLookDown: +eyeLookDown.toFixed(3), eyeLookSide: +eyeLookSide.toFixed(3),
          jawOpen: +jawOpen.toFixed(3), mouthSmile: +mouthSmile.toFixed(3),
        },
      });
      this.lastScores = { focus, bored, confused, label: this.lastScores.label };
    }

    _pushSample(s) {
      this.recent.push({ ...s, t: performance.now() });
      // 只保留最近 1.2 秒
      const cutoff = performance.now() - 1200;
      while (this.recent.length && this.recent[0].t < cutoff) this.recent.shift();
    }

    _postAggregate() {
      if (!this.recent.length) return;
      const n = this.recent.length;
      // absent 樣本（沒臉）獨立統計，不參與三維平均
      const present = this.recent.filter((x) => !x.absent);
      const absentRatio = (n - present.length) / n;
      let focus = 0, bored = 0, confused = 0;
      if (present.length) {
        const avg = (k) => present.reduce((a, x) => a + x[k], 0) / present.length;
        focus = avg("focus");
        bored = avg("bored");
        confused = avg("confused");
      }

      // 校準階段：前 30 秒累積樣本，不上傳
      const elapsedMs = performance.now() - this.startTs;
      if (this.calibrating && elapsedMs < this.CALIB_DURATION_MS) {
        if (present.length) this.calibBuf.push({ focus, bored, confused });
        this._updateCalibUI(elapsedMs);
        return;  // 不發 POST
      }
      if (this.calibrating && elapsedMs >= this.CALIB_DURATION_MS) {
        // 校準完成：算 baseline
        let ok = false;
        if (this.calibBuf.length >= 5) {
          const m = (k) => this.calibBuf.reduce((a, x) => a + x[k], 0) / this.calibBuf.length;
          const v = (k, mean) => this.calibBuf.reduce((a, x) => a + (x[k] - mean) ** 2, 0) / this.calibBuf.length;
          const fm = m("focus"), bm = m("bored"), cm = m("confused");
          this.baseline = {
            focus_mean: +fm.toFixed(3), focus_std: +Math.sqrt(v("focus", fm)).toFixed(3),
            bored_mean: +bm.toFixed(3),
            confused_mean: +cm.toFixed(3),
          };
          try {
            localStorage.setItem("vtuber.attention.baseline", JSON.stringify(this.baseline));
          } catch (_) {}
          console.log("[attention] ✅ 校準完成", this.baseline);
          ok = true;
        } else {
          console.warn("[attention] 校準樣本不足，沿用未修正分數");
          this.baseline = null;
        }
        this.calibrating = false;
        this.calibBuf = [];
        this._removeCalibUI(ok);
      }

      // 套用個人基線修正：把 focus 重新縮放到「相對基線多/少」
      // 但 absent（沒臉）時跳過修正，直接維持 0
      if (this.baseline && absentRatio < 0.5) {
        const std = Math.max(0.05, this.baseline.focus_std);
        // z-score → 映射回 0~1：基線值=0.5、+1σ=0.8、-1σ=0.2
        const z = (focus - this.baseline.focus_mean) / std;
        focus = Math.max(0, Math.min(1, 0.5 + z * 0.3));
        // bored/confused 用差值
        bored = Math.max(0, Math.min(1, bored - this.baseline.bored_mean + 0.3));
        confused = Math.max(0, Math.min(1, confused - this.baseline.confused_mean + 0.3));
      }

      // 主導標籤（absent 優先判斷）
      let label = "neutral";
      if (absentRatio >= 0.5) {
        label = "absent";
        focus = 0; bored = 0; confused = 0;  // 強制歸零，避免 baseline 殘值
      } else {
        const max = Math.max(focus, bored, confused);
        if (max < 0.3) label = "neutral";
        else if (focus === max) label = "focused";
        else if (bored === max) label = "bored";
        else label = "confused";
      }

      const lastRaw = this.recent[this.recent.length - 1].raw || {};
      this.lastScores = { focus, bored, confused, label };

      const payload = {
        label,
        scores: {
          focus: +focus.toFixed(3),
          bored: +bored.toFixed(3),
          confused: +confused.toFixed(3),
        },
        ts: Date.now(),
        raw: { ...lastRaw, samples: n, absent_ratio: +absentRatio.toFixed(3), calibrated: !!this.baseline },
        // device_id 不再从前端帶 (防假冒)，server 從 httpOnly cookie 讀
      };

      fetch(ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        keepalive: true,
      }).catch(() => {/* 靜默 */});
    }
  }

  const tracker = new AttentionTracker();
  window.attentionTracker = tracker;

  function startAfterLogin() {
    setTimeout(() => tracker.start(), 800);
  }

  if (AUTOSTART) {
    // 等 OLV bundle 跑起來再啟動
    window.addEventListener("load", () => setTimeout(() => tracker.start(), 1500));
  } else if (window.__VTUBER_STUDENT__) {
    // 已登入（cookie 存在，student-auth 已在本 module 執行前完成）→ 直接啟動
    startAfterLogin();
  } else {
    // 等待登入成功事件
    document.addEventListener("vtuber:student-ready", startAfterLogin, { once: true });
    console.log("[attention] tracker loaded. 等待登入後自動啟動。");
  }
})();
