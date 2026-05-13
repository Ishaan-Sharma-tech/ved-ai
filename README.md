# 🌌 Aether AI — Your Autonomous Personal AI Operating System (v2.0)

Aether is a next-generation, open-source autonomous agent designed to be your digital second brain. Built on a modular "Multi-Tier" architecture, it bridges the gap between powerful LLMs and your local machine, giving you a seamless voice and text interface for total digital control.

> **Windows-first.** Runs entirely on your machine. No cloud hosting required.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🧠 **Multi-Tier Brain** | Seamlessly switch between "Free Tier" (Groq/Gemini/OpenRouter rotation) and "Pro Tier" (GPT-4o/Claude) via the UI. |
| 🎙️ **Real-time Voice** | Ultra-low latency voice conversations via LiveKit + Gemini, with full tool-calling. |
| 📱 **Telegram Remote** | Securely control your agent and receive notifications on your phone. |
| 🧬 **Self-Evolution** | Ask Aether to build its own tools. It writes, registers, and hot-loads new Python tools autonomously. |
| 🧠 **Knowledge Graph** | Associative long-term memory that extracts facts from your conversations. |
| 🔄 **Key Rotation** | Smart round-robin rotation across multiple free API keys to bypass rate limits. |
| 🛡️ **Auth Guardrails** | High-risk actions (deleting files, sending emails) require your explicit confirmation. |
| 🖼️ **Vision** | Analyze screenshots, images, and documents via AI vision. |
| 🤖 **Agent Swarm** | Run multiple AI agents in parallel for complex, multi-step research tasks. |

---

## 🛠️ Integrated Tool-belt (22+ Tools)

Aether comes pre-equipped with a full operational toolkit:

- **🔍 Web Search** — Real-time research via Tavily
- **📧 Gmail** — Read, search, send, and draft emails
- **📋 Google Tasks** — Add and manage tasks
- **☁️ Google Drive** — Search, download, and create files
- **💻 Code Runner** — Execute Python in a secure sandbox
- **📁 File Manager** — Create, read, list, append, delete files
- **📝 Notes** — Personal note-taking system
- **📹 YouTube Summarizer** — Summarize any YouTube video
- **🎵 Spotify Controller** — Pause/play your music
- **🖥️ System Control** — Volume, brightness, screenshots, app launching
- **🌐 Web Scraper & Playwright** — Scrape pages and automate browsers
- **📰 Tech News** — Fetch trending stories from HackerNews
- **📄 Document Generator** — Generate PDFs and reports
- **🖼️ Image Generator** — Generate images via AI
- **⏰ Scheduler** — Set reminders and recurring tasks
- **🧬 Meta Developer** — Aether builds its own new tools on demand

---

## ⚡ Quick Start (Windows)

### Prerequisites
- **Python 3.10+** — [Download](https://www.python.org/downloads/) (ensure "Add to PATH" is checked)
- **Node.js 18+** — [Download](https://nodejs.org/)
- **Git** — [Download](https://git-scm.com/)

### Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/Ishaan-Sharma-tech/ved-ai.git
    cd ved-ai
    ```

2.  **Run Setup:**
    Double-click **`setup_aether.bat`**. This will:
    - Create a Python virtual environment and install all dependencies.
    - Install Frontend (React/Vite) dependencies.
    - Launch the **Aether Setup Portal** in your browser.

3.  **Configure:**
    Enter your API keys in the Setup Portal and click **Save**.

4.  **Launch:**
    Double-click **`start_ved.bat`** to start all services. Your browser will open to `http://localhost:5173`.

5.  **Stop:**
    Double-click **`stop_ved.bat`** to gracefully shut down all services.

---

## 🔑 API Keys Guide

Aether supports two operating modes:

### Free Tier (No cost)
Get multiple free API keys and Aether rotates between them to avoid rate limits:
| Service | Get Keys From | Env Variables |
|---|---|---|
| Groq | [console.groq.com](https://console.groq.com/) | `GROQ_FREE_1`, `GROQ_FREE_2`, `GROQ_FREE_3` |
| Gemini | [aistudio.google.com](https://aistudio.google.com/) | `GEMINI_FREE_1`, `GEMINI_FREE_2`, `GEMINI_FREE_3` |
| OpenRouter | [openrouter.ai](https://openrouter.ai/) | `OR_FREE_1`, `OR_FREE_2`, `OR_FREE_3` |

### Pro Tier (Paid)
Use a single paid key for higher quality and limits:
| Service | Env Variable |
|---|---|
| OpenAI | `OPENAI_API_KEY` |
| Anthropic Claude | `CLAUDE_API_KEY` |
| Google Gemini (Paid) | `GEMINI_PAID_KEY` |

### Shared Services (Required for specific features)
| Service | Purpose | Env Variable |
|---|---|---|
| [Tavily](https://tavily.com/) | Web Search | `TAVILY_API_KEY` |
| [LiveKit Cloud](https://livekit.io/) | Voice Mode | `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` |
| [Telegram BotFather](https://t.me/BotFather) | Telegram Bot | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_ID` |

---

## 🔗 Google Apps Integration (Gmail, Tasks, Drive)

To enable Google integrations:
1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Create a project, enable the Gmail, Tasks, and Drive APIs.
3.  Create OAuth 2.0 credentials and download the `credentials.json` file.
4.  Place `credentials.json` in the project root directory.
5.  On first use, Aether will open a browser window for you to authorize access.

---

## 📂 Project Structure

```
ved-ai/
├── main.py                 # FastAPI backend entry point
├── telegram_bot.py         # Telegram remote control integration
├── aether_float.py         # Floating desktop widget
├── magic_clipboard.py      # Smart clipboard agent
├── core/                   # Brain: routing, memory, orchestration, privacy
│   ├── orchestrator.py     # Main message processing pipeline
│   ├── task_classifier.py  # Intent classification & tool routing
│   ├── task_planner.py     # Multi-step task planning engine
│   ├── swarm.py            # Multi-agent parallel execution
│   ├── knowledge_graph.py  # Long-term associative memory
│   ├── memory.py           # Conversation history (SQLite)
│   ├── privacy.py          # PII detection & sanitization
│   └── ...routers          # Groq, Gemini, OpenRouter, Paid API routers
├── tools/                  # Modular tool-belt (each tool is a standalone .py)
├── tool_runtime/           # Dynamic tool loader & schema validator
├── voice/                  # LiveKit real-time voice agent
│   └── agent.py            # Gemini-powered voice assistant with tool-calling
├── frontend/               # React + Vite UI
│   └── src/App.jsx         # Main chat, voice orb, and settings interface
├── setup_aether.bat        # One-click first-time setup
├── start_ved.bat           # Launch all services
├── stop_ved.bat            # Stop all services
├── .env.example            # Environment template
└── requirements.txt        # Python dependencies
```

---

## 🛡️ Privacy & Security

- **Local-First:** All logs, conversation history, and your Knowledge Graph are stored locally in `/memory/`.
- **Encrypted Secrets:** Your API keys stay in your local `.env` and are never uploaded.
- **PII Scrubbing:** The privacy engine automatically detects and redacts sensitive data (SSNs, credit cards, API keys) before sending to any LLM.
- **Auth Guardrails:** Destructive actions (deleting files, sending emails, emptying trash) require your explicit vocal or text confirmation.
- **Telegram Lock:** Only your Telegram User ID can interact with the bot.

---

## 🧬 Self-Evolution (Meta Developer)

Aether can build its own tools. Simply ask:
> *"Create a tool called weather_checker that uses the OpenWeatherMap API to get the current weather."*

Aether will:
1. Generate production-quality Python code following its internal tool pattern.
2. Create the JSON schema for the tool's parameters.
3. Save the file to `tools/`, register it in `manifest.json` and `schemas.json`.
4. Hot-load the tool into the running system — no restart needed.

This works from **Text Mode**, **Voice Mode**, and **Telegram**.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

---

**Developed by Ishaan Sharma.**  
*Aether: Sharp. Autonomous. Truly Yours.* 🫡💎🚀
