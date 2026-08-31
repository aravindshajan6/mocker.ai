#!/usr/bin/env bash
# Generate /opt/mocker/.env with strong random secrets.
#
# A script rather than hand-editing: these values are long, repeated across fields, and a mistyped
# character inside a connection string produces a confusing failure at boot rather than an obvious
# one. Run it ON THE VPS. It refuses to overwrite an existing .env.
set -euo pipefail

TARGET="${1:-/opt/mocker/.env}"
if [[ -e "$TARGET" ]]; then
  echo "refusing to overwrite $TARGET — move it aside first if you really mean to" >&2
  exit 1
fi
mkdir -p "$(dirname "$TARGET")"

# base64 then strip URL-significant characters: these end up inside a postgres:// DSN.
rand() { openssl rand -base64 "$1" | tr -d '\n=+/:@?#'; }

POSTGRES_PASSWORD="$(rand 24)"
JWT_SECRET="$(rand 48)"
ADMIN_PASSWORD="$(rand 18)"
SEED_USER_PASSWORD="$(rand 12)"
ADMIN_TOKEN="$(rand 24)"

umask 077
cat > "$TARGET" <<INNER
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
JWT_SECRET=${JWT_SECRET}

ADMIN_EMAIL=admin@mocker.app
ADMIN_PASSWORD=${ADMIN_PASSWORD}
SEED_USER_EMAIL=aswathi@gmail.com
SEED_USER_PASSWORD=${SEED_USER_PASSWORD}
DEMO_EMAIL=demo@mocker.app
DEMO_PASSWORD=

LLM_PROVIDER=groq
LLM_API_KEY=
LLM_MODEL=
LLM_BASE_URL=

CURRENT_AFFAIRS_ENABLED=true
CURRENT_AFFAIRS_HOUR_IST=6
CURRENT_AFFAIRS_TARGET=15
VERIFY_ENABLED=true
VERIFY_HOUR_IST=3
VERIFY_PER_NIGHT=400
STAGING_ENABLED=true
STAGING_HOUR_IST=2

REMINDERS_ENABLED=true
VAPID_SUBJECT=mailto:you@example.com
TELEGRAM_BOT_TOKEN=
TELEGRAM_BOT_USERNAME=

ADMIN_TOKEN=${ADMIN_TOKEN}
INNER
chmod 600 "$TARGET"

# Printed once, to the terminal only — these are never echoed again and are not in the repo.
cat <<SUMMARY

Wrote $TARGET (mode 600).

Sign-in credentials — copy these somewhere safe NOW:

  admin      admin@mocker.app        ${ADMIN_PASSWORD}
  learner    aswathi@gmail.com       ${SEED_USER_PASSWORD}

The demo account is disabled (DEMO_PASSWORD empty). Set it if you want a public login.

Still to fill in by hand:
  LLM_API_KEY     — without it, current affairs falls back to heuristics and
                    "Explain this more" is unavailable. Nothing crashes.
  VAPID_SUBJECT   — a contact mailto: for push notifications.

SUMMARY
