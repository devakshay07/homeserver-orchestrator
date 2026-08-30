# Project Generation Rules

## Architecture Preferences
- Use clean architecture.
- Modularize components.
- Favor dependency injection where applicable.

## Coding Principles
- Keep resource consumption low.
- Optimize for edge-device constraints (minimal RAM, fewer background processes).
- Write robust error handling and recovery.
- Include structured logging.

## Tech Stack Defaults
- Unless specified, prefer Python 3.11+ for backend.
- Use lightweight dependencies.
- For UI, prefer minimal frameworks or raw HTML/JS if appropriate.
- Database: prefer SQLite for single-node edge devices.

## Requirements
- Always include a comprehensive README.md.
- Always include a docker-compose.yml and Dockerfile if applicable.
- Include automated tests.
