# Deployment Guide

The HomeServer Orchestrator is designed to run efficiently on edge hardware (e.g., Raspberry Pi, old laptops running Lubuntu).

## Docker (Recommended)

Running via Docker Compose isolates the environment and ensures dependencies are cleanly managed without polluting your host OS.

1. Install [Docker Engine](https://docs.docker.com/engine/install/) and `docker-compose`.
2. Clone the repository.
3. Configure your `.env` file (see [Configuration](configuration.md)).
4. Start the service in detached mode:
   ```bash
   docker-compose up -d
   ```
5. To view live logs:
   ```bash
   docker-compose logs -f
   ```

*Note: Ensure the `./data` and `./logs` directories are correctly mounted as volumes to preserve SQLite state and ChromaDB memory across container restarts.*

## Bare Metal (Systemd)

If you prefer running natively to save container overhead:

1. Clone the repository.
2. Run the installer script to create a virtual environment and install dependencies:
   ```bash
   chmod +x install.sh
   ./install.sh
   ```
3. Configure your `.env` file.
4. (Optional) Run the healthcheck script to verify connectivity to Telegram and Gemini APIs:
   ```bash
   ./healthcheck.sh
   ```
5. Run the application:
   ```bash
   source venv/bin/activate
   python src/main.py
   ```
   *(We recommend setting this up as a `systemd` service for automatic restarts on boot).*
