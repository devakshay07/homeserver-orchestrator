#!/bin/bash
set -e

SERVICE_FILE=/etc/systemd/system/homeserver.service
APP_DIR=$(pwd)
USER=$(whoami)

echo "Setting up systemd service for user $USER at $APP_DIR"

sudo cat << EOL > $SERVICE_FILE
[Unit]
Description=HomeServer Orchestrator
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=$APP_DIR/venv/bin/python src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOL

sudo systemctl daemon-reload
sudo systemctl enable homeserver
sudo systemctl start homeserver

echo "systemd service 'homeserver' installed and started."
