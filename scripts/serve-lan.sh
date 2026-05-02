#!/usr/bin/env bash
# Serve the weahist web app on the local network so other devices
# (phone, tablet, another laptop on the same Wi-Fi) can reach it.
#
# Usage:
#   scripts/serve-lan.sh             # default port 8000
#   scripts/serve-lan.sh 9000        # custom port
#   PORT=9000 scripts/serve-lan.sh   # custom port via env

set -euo pipefail

PORT="${1:-${PORT:-8000}}"
HOST="0.0.0.0"

# Best-effort: print the laptop's primary LAN IP so you know what
# URL to type on your phone.
lan_ip="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
if [[ -z "${lan_ip}" ]]; then
  lan_ip="$(ip -4 -o addr show scope global 2>/dev/null \
    | awk '{print $4}' | cut -d/ -f1 | head -n1 || true)"
fi

echo "weahist — LAN server"
echo "  local:   http://127.0.0.1:${PORT}"
if [[ -n "${lan_ip}" ]]; then
  echo "  network: http://${lan_ip}:${PORT}"
else
  echo "  network: http://<your-lan-ip>:${PORT}  (could not auto-detect)"
fi
echo "  stop:    Ctrl+C"
echo

# No --reload on purpose: filesystem watching is dev-only and not
# appropriate when exposing the server on the LAN.
exec uv run uvicorn weahist.api.app:app --host "${HOST}" --port "${PORT}"
