#!/bin/bash
# Every teammate runs this once after cloning:  ./scripts/install_hooks.sh
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cat > "$ROOT/.git/hooks/pre-commit" <<'EOF'
#!/bin/bash
exec "$(git rev-parse --show-toplevel)/scripts/check_secrets.sh"
EOF
chmod +x "$ROOT/.git/hooks/pre-commit" "$ROOT/scripts/check_secrets.sh"
echo "Secret check installed: commits containing API keys or .env files will be blocked."
