#!/bin/bash
set -e

echo "Starting HomeServer installation for Lubuntu..."

# 1. Update and install system deps
sudo apt update
sudo apt install -y python3.11 python3-pip python3-venv git nodejs npm sqlite3 libsqlite3-dev

# 2. Install npm deps
sudo npm install -g markdown-link-check

# 3. Setup virtual env
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. Setup .env
if [ ! -f .env ]; then
    cp .env.example .env
    echo ".env created. Please fill in your tokens and re-run installation or validation."
fi

# 5. Validate .env
python installer/validate_env.py || { echo "Environment validation failed. Please fix .env and try again."; exit 1; }

# 6. Install agy (assuming it's a pip package or bash script)
# For now, we mock this as just a pip install if it's python, or echo instruction
echo "Please ensure Google Antigravity (agy) is installed and authenticated."

echo "Installation complete."
