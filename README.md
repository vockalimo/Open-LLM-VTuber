![](./assets/banner.jpg)

<h1 align="center">Open-LLM-VTuber</h1>
<h3 align="center">

[![GitHub release](https://img.shields.io/github/v/release/Open-LLM-VTuber/Open-LLM-VTuber)](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber/releases) 
[![license](https://img.shields.io/github/license/Open-LLM-VTuber/Open-LLM-VTuber)](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber/blob/master/LICENSE) 
[![CodeQL](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber/actions/workflows/codeql.yml/badge.svg)](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber/actions/workflows/codeql.yml)
[![Ruff](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber/actions/workflows/ruff.yml/badge.svg)](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber/actions/workflows/ruff.yml)
[![Docker](https://img.shields.io/badge/Open-LLM-VTuber%2FOpen--LLM--VTuber-%25230db7ed.svg?logo=docker&logoColor=blue&labelColor=white&color=blue)](https://hub.docker.com/r/Open-LLM-VTuber/open-llm-vtuber) 
[![QQ User Group](https://img.shields.io/badge/QQ_User_Group-792615362-white?style=flat&logo=qq&logoColor=white)](https://qm.qq.com/q/ngvNUQpuKI)
[![Static Badge](https://img.shields.io/badge/Join%20Chat-Zulip?style=flat&logo=zulip&label=Zulip(dev-community)&color=blue&link=https%3A%2F%2Folv.zulipchat.com)](https://olv.zulipchat.com)

> **📢 v2.0 Development**: We are focusing on Open-LLM-VTuber v2.0 — a complete rewrite of the codebase. v2.0 is currently in its early discussion and planning phase. We kindly ask you to refrain from opening new issues or pull requests for feature requests on v1. To participate in the v2 discussions or contribute, join our developer community on [Zulip](https://olv.zulipchat.com). Weekly meeting schedules will be announced on Zulip. We will continue fixing bugs for v1 and work through existing pull requests.

[![BuyMeACoffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/yi.ting)
[![](https://dcbadge.limes.pink/api/server/3UDA8YFDXx)](https://discord.gg/3UDA8YFDXx)

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Open-LLM-VTuber/Open-LLM-VTuber)

ENGLISH README | [中文 README](./README.CN.md) | [한국어 README](./README.KR.md) | [日本語 README](./README.JP.md)

[Documentation](https://open-llm-vtuber.github.io/docs/quick-start) | [![Roadmap](https://img.shields.io/badge/Roadmap-GitHub_Project-yellow)](https://github.com/orgs/Open-LLM-VTuber/projects/2)

<a href="https://trendshift.io/repositories/12358" target="_blank"><img src="https://trendshift.io/api/badge/repositories/12358" alt="Open-LLM-VTuber%2FOpen-LLM-VTuber | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

</h3>


> 常见问题 Common Issues doc (Written in Chinese): https://docs.qq.com/pdf/DTFZGQXdTUXhIYWRq
>
> User Survey: https://forms.gle/w6Y6PiHTZr1nzbtWA
>
> 调查问卷(中文): https://wj.qq.com/s2/16150415/f50a/



> :warning: This project is in its early stages and is currently under **active development**.

> :warning: If you want to run the server remotely and access it on a different machine, such as running the server on your computer and access it on your phone, you will need to configure `https`, because the microphone on the front end will only launch in a secure context (a.k.a. https or localhost). See [MDN Web Doc](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia). Therefore, you should configure https with a reverse proxy to access the page on a remote machine (non-localhost).



## ⭐️ What is this project?


**Open-LLM-VTuber** is a unique **voice-interactive AI companion** that not only supports **real-time voice conversations**  and **visual perception** but also features a lively **Live2D avatar**. All functionalities can run completely offline on your computer!

You can treat it as your personal AI companion — whether you want a `virtual girlfriend`, `boyfriend`, `cute pet`, or any other character, it can meet your expectations. The project fully supports `Windows`, `macOS`, and `Linux`, and offers two usage modes: web version and desktop client (with special support for **transparent background desktop pet mode**, allowing the AI companion to accompany you anywhere on your screen).

Although the long-term memory feature is temporarily removed (coming back soon), thanks to the persistent storage of chat logs, you can always continue your previous unfinished conversations without losing any precious interactive moments.

In terms of backend support, we have integrated a rich variety of LLM inference, text-to-speech, and speech recognition solutions. If you want to customize your AI companion, you can refer to the [Character Customization Guide](https://open-llm-vtuber.github.io/docs/user-guide/live2d) to customize your AI companion's appearance and persona.

The reason it's called `Open-LLM-Vtuber` instead of `Open-LLM-Companion` or `Open-LLM-Waifu` is because the project's initial development goal was to use open-source solutions that can run offline on platforms other than Windows to recreate the closed-source AI Vtuber `neuro-sama`.

### 👀 Demo
| ![](assets/i1.jpg) | ![](assets/i2.jpg) |
|:---:|:---:|
| ![](assets/i3.jpg) | ![](assets/i4.jpg) |


## ✨ Features & Highlights

- 🖥️ **Cross-platform support**: Perfect compatibility with macOS, Linux, and Windows. We support NVIDIA and non-NVIDIA GPUs, with options to run on CPU or use cloud APIs for resource-intensive tasks. Some components support GPU acceleration on macOS.

- 🔒 **Offline mode support**: Run completely offline using local models - no internet required. Your conversations stay on your device, ensuring privacy and security.

- 💻 **Attractive and powerful web and desktop clients**: Offers both web version and desktop client usage modes, supporting rich interactive features and personalization settings. The desktop client can switch freely between window mode and desktop pet mode, allowing the AI companion to be by your side at all times.

- 🎯 **Advanced interaction features**:
  - 👁️ Visual perception, supporting camera, screen recording and screenshots, allowing your AI companion to see you and your screen
  - 🎤 Voice interruption without headphones (AI won't hear its own voice)
  - 🫱 Touch feedback, interact with your AI companion through clicks or drags
  - 😊 Live2D expressions, set emotion mapping to control model expressions from the backend
  - 🐱 Pet mode, supporting transparent background, global top-most, and mouse click-through - drag your AI companion anywhere on the screen
  - 💭 Display AI's inner thoughts, allowing you to see AI's expressions, thoughts and actions without them being spoken
  - 🗣️ AI proactive speaking feature
  - 💾 Chat log persistence, switch to previous conversations anytime
  - 🌍 TTS translation support (e.g., chat in Chinese while AI uses Japanese voice)

- 🧠 **Extensive model support**:
  - 🤖 Large Language Models (LLM): Ollama, OpenAI (and any OpenAI-compatible API), Gemini, Claude, Mistral, DeepSeek, Zhipu AI, GGUF, LM Studio, vLLM, etc.
  - 🎙️ Automatic Speech Recognition (ASR): sherpa-onnx, FunASR, Faster-Whisper, Whisper.cpp, Whisper, Groq Whisper, Azure ASR, etc.
  - 🔊 Text-to-Speech (TTS): sherpa-onnx, pyttsx3, MeloTTS, Coqui-TTS, GPTSoVITS, Bark, CosyVoice, Edge TTS, Fish Audio, Azure TTS, etc.

- 🔧 **Highly customizable**:
  - ⚙️ **Simple module configuration**: Switch various functional modules through simple configuration file modifications, without delving into the code
  - 🎨 **Character customization**: Import custom Live2D models to give your AI companion a unique appearance. Shape your AI companion's persona by modifying the Prompt. Perform voice cloning to give your AI companion the voice you desire
  - 🧩 **Flexible Agent implementation**: Inherit and implement the Agent interface to integrate any Agent architecture, such as HumeAI EVI, OpenAI Her, Mem0, etc.
  - 🔌 **Good extensibility**: Modular design allows you to easily add your own LLM, ASR, TTS, and other module implementations, extending new features at any time


## 👥 User Reviews
> Thanks to the developer for open-sourcing and sharing the girlfriend for everyone to use
> 
> This girlfriend has been used over 100,000 times


## 🚀 Quick Start

Please refer to the [Quick Start](https://open-llm-vtuber.github.io/docs/quick-start) section in our documentation for installation.



## ☝ Update
> :warning: `v1.0.0` has breaking changes and requires re-deployment. You *may* still update via the method below, but the `conf.yaml` file is incompatible and most of the dependencies needs to be reinstalled with `uv`. For those who came from versions before `v1.0.0`, I recommend deploy this project again with the [latest deployment guide](https://open-llm-vtuber.github.io/docs/quick-start).

Please use `uv run update.py` to update if you installed any versions later than `v1.0.0`.

## 😢 Uninstall  
Most files, including Python dependencies and models, are stored in the project folder.

However, models downloaded via ModelScope or Hugging Face may also be in `MODELSCOPE_CACHE` or `HF_HOME`. While we aim to keep them in the project's `models` directory, it's good to double-check.  

Review the installation guide for any extra tools you no longer need, such as `uv`, `ffmpeg`, or `deeplx`.  

## 🤗 Want to contribute?
Checkout the [development guide](https://docs.llmvtuber.com/docs/development-guide/overview).


# 🎉🎉🎉 Related Projects

[ylxmf2005/LLM-Live2D-Desktop-Assitant](https://github.com/ylxmf2005/LLM-Live2D-Desktop-Assitant)
- Your Live2D desktop assistant powered by LLM! Available for both Windows and MacOS, it senses your screen, retrieves clipboard content, and responds to voice commands with a unique voice. Featuring voice wake-up, singing capabilities, and full computer control for seamless interaction with your favorite character.






## 📜 Third-Party Licenses

### Live2D Sample Models Notice

This project includes Live2D sample models provided by Live2D Inc. These assets are licensed separately under the Live2D Free Material License Agreement and the Terms of Use for Live2D Cubism Sample Data. They are not covered by the MIT license of this project.

This content uses sample data owned and copyrighted by Live2D Inc. The sample data are utilized in accordance with the terms and conditions set by Live2D Inc. (See [Live2D Free Material License Agreement](https://www.live2d.jp/en/terms/live2d-free-material-license-agreement/) and [Terms of Use](https://www.live2d.com/eula/live2d-sample-model-terms_en.html)).

Note: For commercial use, especially by medium or large-scale enterprises, the use of these Live2D sample models may be subject to additional licensing requirements. If you plan to use this project commercially, please ensure that you have the appropriate permissions from Live2D Inc., or use versions of the project without these models.


## Contributors
Thanks our contributors and maintainers for making this project possible.

<a href="https://github.com/Open-LLM-VTuber/Open-LLM-VTuber/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=Open-LLM-VTuber/Open-LLM-VTuber" />
</a>


## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Open-LLM-VTuber/open-llm-vtuber&type=Date)](https://star-history.com/#Open-LLM-VTuber/open-llm-vtuber&Date)

---

## 🛠️ Lalacube 部署維護說明

> 本節僅適用於 `vockalimo/Open-LLM-VTuber` fork，記錄 lalacube 自訂部署的注意事項。

### 架構概覽

```
frontend/               ← git submodule（唯讀，指向 Open-LLM-VTuber-Web build branch）
frontend-overlay/       ← lalacube 自訂 UI（這裡改，不要動 submodule）
  ├── index.html        ← 自訂首頁（遊戲按鈕、角色切換、學生登入、繁中語言設定）
  ├── character-switch.js
  ├── attention.js
  └── student-auth.js
dockerfile              ← build 時將 frontend-overlay/ 複製覆蓋 frontend/
```

Docker build 流程：
1. `git submodule update --init --recursive` → 取出 `frontend/`（pinned commit）
2. `frontend-overlay/` 的檔案複製蓋過 `frontend/`
3. 修補 `main-*.js`：`DEFAULT_BASE_URL` 改為 `""`，`DEFAULT_WS_URL` 改為相對 host
4. **assert 驗證**：若 `127.0.0.1` 仍存在於 JS bundle → build 立即失敗（上游改了變數名，需手動更新 patch）

### 修改前端 UI

**不要直接修改 `frontend/`（submodule，改了不會進 git）**

正確做法：
```bash
# 修改 frontend-overlay/ 裡的檔案
vim frontend-overlay/index.html

# commit & push
git add frontend-overlay/
git commit -m "feat: ..."
git push lalacube main
# → CI 自動部署
```

### 升級 frontend submodule

submodule 目前 pinned 到 `06a659b`（build branch），**不要隨意升級**。
升級前務必先確認上游 JS bundle 的變數名稱沒有改變（否則 assert 會在 build 時報錯）。

```bash
# 1. 確認新版本的 main-*.js 仍有 DEFAULT_BASE_URL / DEFAULT_WS_URL
# 2. 升級 pointer
git -C frontend fetch
git -C frontend checkout <新 commit hash>
git add frontend
git commit -m "chore: upgrade frontend submodule to <hash>"
git push lalacube main

# 3. 觀察 CI build log：
#    ✅ main.js patched OK
#    ✅ patch verification passed (no 127.0.0.1 in JS)
#    → 表示 patch 成功
#
#    PATCH FAILED: 127.0.0.1 still in main-*.js
#    → 上游改了變數名，需更新 dockerfile 裡的 patch strings
```

### GCS 靜態資產

背景圖和遊戲素材存放於 `gs://lalacube-assets`（公開讀取），build 時自動下載：
- `vtuber/backgrounds/` → `/app/backgrounds/`
- `vtuber/game_assets/` → `/app/game_assets/`

上傳新素材：
```bash
gsutil cp my-bg.jpg gs://lalacube-assets/vtuber/backgrounds/
# 重新 build image 後自動生效
```

### 部署 CI/CD

- Repository: `vockalimo/Open-LLM-VTuber`（Open-LLM-VTuber 本體）
- CI/CD: `AIShopping` repo 的 `.github/workflows/deploy.yml`，push 到 `vockalimo/Open-LLM-VTuber` 後在 AIShopping 手動觸發（`gh workflow run deploy.yml -f services=vtuber`）或由路徑過濾自動觸發
- GCP VM: `aishopping-meili`，`asia-east1-a`

### vtuber-conf 設定（AIShopping repo）

VAD 靈敏度設定位於 `AIShopping/vtuber-conf/conf.yaml`：
```yaml
prob_threshold: 0.3    # 降低 → 更容易觸發（預設 0.4）
db_threshold: 50       # 降低 → 更容易觸發（預設 60）
required_hits: 2       # 降低 → 更容易觸發（預設 3）
```





