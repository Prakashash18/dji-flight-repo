#!/usr/bin/env bash
# Stops the Cloudflare tunnel and the backend.
#
#   ./deploy/stop.sh             # stop both
#   ./deploy/stop.sh --tunnel    # take it off the internet, keep serving locally

set -uo pipefail
TUNNEL_ONLY=0
[[ "${1:-}" == "--tunnel" ]] && TUNNEL_ONLY=1

if pgrep -f "cloudflared tunnel run" >/dev/null 2>&1; then
  pkill -f "cloudflared tunnel run"; sleep 2
  pgrep -f "cloudflared tunnel run" >/dev/null 2>&1 \
    && echo "  ✗ tunnel still running" || echo "  ✓ tunnel stopped (coastalpatrol.app now returns 1033)"
else
  echo "  • tunnel was not running"
fi

if [[ $TUNNEL_ONLY -eq 1 ]]; then
  echo "  • backend left running on :8000"
  exit 0
fi

if lsof -ti:8000 >/dev/null 2>&1; then
  # Graceful first so worker pools shut down cleanly, then force if needed.
  pkill -f "backend/venv/bin/python main.py" 2>/dev/null
  sleep 3
  lsof -ti:8000 2>/dev/null | xargs -r kill 2>/dev/null
  sleep 1
  lsof -ti:8000 >/dev/null 2>&1 && echo "  ✗ port 8000 still in use" || echo "  ✓ backend stopped"
else
  echo "  • backend was not running"
fi
