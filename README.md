# 🏡 HomeServer Orchestrator
**Your Personal AI Software Factory.**

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)

**HomeServer Orchestrator** turns any old laptop, Raspberry Pi, or edge device into a fully autonomous software development pipeline. 

No dashboards, no complicated setups, and no cloud hosting fees. Just open Telegram, text your bot an idea for an app, and let it do the rest.

---

## ✨ How It Works

1. **📱 You text an idea:** *"Build me a Python script that checks the weather every morning and sends me a summary."*
2. **🤖 The AI gets to work:** Your home server wakes up, writes a technical spec, and generates the entire codebase autonomously.
3. **🛡️ It tests itself safely:** The code is placed inside a locked-down, secure Docker sandbox where the AI tests it for bugs, formatting, and leaked secrets.
4. **✅ You get a Pull Request:** The bot messages you back on Telegram with a link to a finished GitHub Pull Request, ready for your approval.

## 🌟 Why This is Awesome

* **Chat to Build:** Control your entire software factory from anywhere using Telegram. You can queue up ideas while on a walk, and they'll be coded by the time you get home.
* **Smart Memory:** The system remembers past projects and past mistakes. If it fails a test today, it uses that context to avoid the same bug tomorrow.
* **Bulletproof Reliability:** Power outage? Wi-Fi dropped? No problem. The system constantly saves its progress and picks up exactly where it left off when it boots back up.
* **Bank-Grade Safety:** All AI-generated code is aggressively tested inside an isolated, network-less container before it ever touches your GitHub or host machine.

---

## 🚀 Quick Start

### 1. What You Need
- Docker installed on your device
- A Telegram Bot Token (get one for free from [@BotFather](https://t.me/botfather))
- A free Gemini API Key
- A GitHub Personal Access Token

### 2. Run It
Clone this repository to your home server or old laptop:
```bash
git clone https://github.com/devakshay07/homeserver-orchestrator.git
cd homeserver-orchestrator
```

Copy the example configuration file and paste in your tokens:
```bash
cp .env.example .env
nano .env
```

Start the factory:
```bash
docker-compose up -d
```
*That's it! Open Telegram, message your bot `/start`, and tell it what you want to build.*

---

## 📖 Learn More

Want to look under the hood? Check out our `docs/` folder for the technical details:
- [Architecture & Design](docs/architecture.md)
- [Configuration Guide](docs/configuration.md)
- [Telegram Commands](docs/commands.md)

## 🤝 Contributing
Have an idea to make this even better? Pull requests are always welcome! 

## 📝 License
This project is open-source and licensed under the [MIT License](LICENSE).
