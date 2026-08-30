# 🏡 HomeServer Autonomous Orchestrator

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)

**HomeServer Orchestrator** is a highly resilient, fully autonomous software generation pipeline designed to run on low-end edge devices (like a Lubuntu laptop or Raspberry Pi). 

Send a software idea via Telegram, and the orchestrator will:
1. Brainstorm and generate a detailed Technical Specification.
2. Synthesize the entire application codebase autonomously.
3. Run a strict Quality Gate (linting, static analysis, secret scanning, and automated tests).
4. Commit and push the code to GitHub.
5. Create a Pull Request and notify you on Telegram for final approval.

## 🌟 Key Features

* **📱 Telegram Native Interface:** Command, control, and monitor your entire development pipeline from anywhere using a Telegram Bot.
* **🧠 AI-Powered Development:** Leverages Gemini AI for architectural specs and code generation.
* **🛡️ Hardened Quality Gates:** Automatically runs `ruff`, `mypy`, `detect-secrets`, and `pytest` on generated code, preventing broken code from reaching your repo.
* **💾 Edge-Optimized & Robust:** Uses a lightweight SQLite persistent queue, ChromaDB for vector memory, and fine-grained state checkpoints. If the device reboots or loses power, tasks resume exactly where they left off without wasting API calls.
* **🔁 Auto-Degradation & Quota Management:** Built-in API key rotation and model fallbacks (e.g., `gemini-2.5-flash` to `gemini-2.0-flash`) ensure uninterrupted operation.
* **📅 Cron Scheduling:** Schedule recurring generation tasks (e.g., daily scrapers, weekly reports) effortlessly.

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.11+
- [Docker](https://docs.docker.com/engine/install/) & Docker Compose (if deploying via container)
- A Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Gemini API Key(s)
- GitHub Personal Access Token (PAT)

### 2. Installation

Clone the repository:
```bash
git clone https://github.com/yourusername/homeserver-orchestrator.git
cd homeserver-orchestrator
```

Copy the example environment file and fill in your credentials:
```bash
cp .env.example .env
nano .env
```

### 3. Running the Server

**Using Docker (Recommended for Edge Devices):**
```bash
docker-compose up -d
```

**Bare-Metal / Local:**
```bash
./install.sh
source venv/bin/activate
python src/main.py
```

## 📖 Documentation

For deep-dive documentation, please refer to the `docs/` folder:
- [Architecture & Design](docs/architecture.md)
- [Configuration Guide](docs/configuration.md)
- [Telegram Commands](docs/commands.md)
- [Deployment & Setup](docs/deployment.md)
- [Troubleshooting & FAQ](docs/troubleshooting.md)

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](#).

## 📝 License

This project is [MIT](LICENSE) licensed.
