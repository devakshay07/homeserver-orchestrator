# Stealth Social Media Management (Playwright)

## Core Philosophy
This module bypasses restricted official APIs by using Playwright (headless Chromium) to mimic human behavior. It operates strictly on the host's residential IP and relies on stochastic delays to avoid bot detection.

## Authentication (The Session Vault)
Never hardcode usernames or passwords. The system must use **Browser Context Injection**:
1. Provide a script (`login_ig.py`) that opens a **headed** (visible) Playwright browser.
2. The user logs in manually, solving any 2FA, Captchas, or "Is this you?" prompts.
3. The script extracts the full `browser_context` (cookies, local storage) and saves it to `data/ig_session.json` or the SQLite database.
4. The headless outreach agent loads this context file. To Instagram, the headless bot appears identical to the trusted browser session.

## Anti-Ban Guardrails (Mandatory)
- **Stochastic Delays**: Use Gaussian delays between actions (e.g., 45s to 4m). Never use fixed `time.sleep()`.
- **Typing Jitter**: Type characters one-by-one with 50ms-200ms randomized delays. Never paste text.
- **Daily Hard Quotas**: Max 20 new DMs, 30 follows, 100 profile scrapes per day.
- **Ghost Interactions**: Randomly scroll profiles and drop likes before sending a DM to simulate authentic discovery.

## Database Schema (SQLite)
- `leads`: handle (PK), bio, recent_content, is_active, qualification_score, niche_reasoning, contacted (bool), contacted_at.
- `outreach_log`: id (PK), lead_handle (FK), message_sent, sent_at.
- Enforce UNIQUE constraints on handles to prevent duplicate DMs.

## Execution Pipeline
1. **Shallow Scrape**: Extract handles from target sources.
2. **Deep Scrape**: Extract bio, last 3 post captions, and last post date. Discard inactive users.
3. **Qualification**: Pass scraped data + `outreach_persona.md` to Gemini. Score 1-10 based on niche fit.
4. **Drafting**: Gemini drafts a personalized DM referencing recent content and fusing the user's persona/offer.
5. **Outreach**: Playwright sends the drafted DM using typing jitter and marks `contacted=True`.

## Operational Resilience & Monitoring (Mandatory)
When building this agent, you MUST include the following operational safeguards:

1. **Session Expiration Circuit Breaker**:
   - The agent must check the URL and page elements upon loading Instagram.
   - If a login page (`/accounts/login/`) or a "You've been logged out" modal is detected, the agent MUST immediately pause all execution.
   - It must send an urgent Telegram alert: `🚨 Instagram session expired. Execution paused. Please re-run the login script to refresh the session.`
   - This prevents the bot from blindly looping and triggering account locks.

2. **Daily Automated Backups**:
   - The agent's `docker-compose.yml` or internal cron system must include a backup routine.
   - Every night (e.g., 2:00 AM), it must zip the entire `data/` directory (containing the SQLite databases and session files) and store it in a `backups/` folder.
   - It should retain the last 7 days of backups and automatically delete older ones to save disk space.

3. **End-of-Day Telegram Reports**:
   - The agent must maintain a daily counter of actions in memory or SQLite.
   - At a specified time (e.g., 8:00 PM), it must send a clean summary to the user via Telegram.
   - Format: `📊 Daily Stealth Report:
- 🔍 Scraped: 120 leads
- 📩 Sent: 20 DMs
- 💬 Replies: 3
- ⚠️ Errors: 0`
   - This ensures the user has full visibility without needing to SSH into the server to read logs.