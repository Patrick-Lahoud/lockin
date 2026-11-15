#!/bin/bash
# Blocks a commit if it contains an API key, bot token or a .env file.
# Installed as a git pre-commit hook by scripts/install_hooks.sh (every teammate runs it once).
# Manual full scan:  scripts/check_secrets.sh --all
set -uo pipefail

PATTERNS=(
  'AIza[0-9A-Za-z_-]{35}'                       # Google API key (classic)
  'AQ\.[0-9A-Za-z_-]{30,}'                      # Google API key (new AQ. format)
  '[0-9]{8,10}:AA[0-9A-Za-z_-]{30,}'            # Telegram bot token
  'sk-[A-Za-z0-9_-]{20,}'                       # OpenAI / Anthropic style keys
  'gh[pousr]_[A-Za-z0-9]{30,}'                  # GitHub tokens
  '-----BEGIN [A-Z ]*PRIVATE KEY-----'          # private keys
  '(GEMINI_API_KEY|TELEGRAM_BOT_TOKEN)=[A-Za-z0-9._:-]{20,}'  # a filled-in secret line
)
REGEX="$(IFS='|'; echo "${PATTERNS[*]}")"
fail=0

if [[ "${1:-}" == "--all" ]]; then
  files=$(git ls-files)
  content_cmd() { cat -- "$1" 2>/dev/null; }
else
  files=$(git diff --cached --name-only --diff-filter=ACMR)
  content_cmd() { git show ":$1" 2>/dev/null; }
fi

for f in $files; do
  base="$(basename "$f")"
  if [[ "$base" == ".env" || ( "$base" == .env.* && "$base" != ".env.example" ) || "$base" == *.pem || "$base" == *.key || "$base" == ".owner.json" ]]; then
    echo "✋ BLOCKED: $f is a secrets file and must never be committed."
    fail=1
    continue
  fi
  if content_cmd "$f" | grep -En -- "$REGEX" >/dev/null 2>&1; then
    echo "✋ BLOCKED: $f looks like it contains a secret:"
    content_cmd "$f" | grep -En -- "$REGEX" | sed -E 's/(.{0,30}).*/  line \1… (hidden)/' | head -5
    fail=1
  fi
done

if [[ $fail -ne 0 ]]; then
  echo
  echo "Move secrets to agent/.env (git ignores it). If it's a false alarm, fix the pattern in scripts/check_secrets.sh."
  exit 1
fi
[[ "${1:-}" == "--all" ]] && echo "No secrets found in tracked files ✓"
exit 0
