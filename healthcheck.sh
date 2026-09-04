#!/bin/bash
# healthcheck.sh - Validates environment and dependencies

# Source environment safely
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

echo "Running health checks..."

# Test Python version
python3 -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11+ required'" || exit 1

# Test dependencies
node --version >/dev/null || exit 1
git --version >/dev/null || exit 1
sqlite3 --version >/dev/null || exit 1

# Test Telegram API
TG_OK=$(curl -sf "https://api.telegram.org/bot${TELEGRAM_TOKEN}/getMe" | python3 -c "import sys,json; d=json.load(sys.stdin); print('ok' if d.get('ok') else 'fail')" 2>/dev/null || echo "fail")
if [ "$TG_OK" != "ok" ]; then
    echo "FAIL: Telegram token invalid or unreachable"
    exit 1
fi

# Extract first Gemini key from GEMINI_KEYS JSON array
if [ -n "$GEMINI_KEYS" ]; then
    GEMINI_KEY_1=$(python3 -c "import json, os; keys=json.loads(os.environ.get('GEMINI_KEYS', '[]')); print(keys[0] if keys else '')")
    if [ -n "$GEMINI_KEY_1" ]; then
        GM_OK=$(curl -sf -H "x-goog-api-key: ${GEMINI_KEY_1}" "https://generativelanguage.googleapis.com/v1beta/models" | python3 -c "import sys,json; print('ok' if 'models' in json.load(sys.stdin) else 'fail')" 2>/dev/null || echo "fail")
        if [ "$GM_OK" != "ok" ]; then
            echo "FAIL: Gemini API unreachable or key invalid"
            exit 1
        fi
    fi
fi

echo "All health checks passed."
