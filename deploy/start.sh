#!/usr/bin/env bash
# Starts the backend and the Cloudflare tunnel, in that order.
#
#   ./deploy/start.sh            # backend + tunnel (public)
#   ./deploy/start.sh --local    # backend only, no tunnel
#
# Safe to re-run: anything already running is left alone.

set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
LOGS="$ROOT/deploy/logs"; mkdir -p "$LOGS"
LOCAL_ONLY=0
[[ "${1:-}" == "--local" ]] && LOCAL_ONLY=1

# ------------------------------------------------------------------ backend ---
if lsof -ti:8000 >/dev/null 2>&1; then
  echo "• backend already running on :8000"
else
  echo "• starting backend…"
  ( cd backend && HOST=0.0.0.0 nohup ./venv/bin/python main.py > "$LOGS/backend.log" 2>&1 & )
fi

for i in $(seq 1 40); do
  if curl -s -o /dev/null -m 3 -w "%{http_code}" http://127.0.0.1:8000/api/demo 2>/dev/null | grep -q 200; then
    echo "  ✓ backend healthy"; break
  fi
  [[ $i -eq 40 ]] && { echo "  ✗ backend did not start — see $LOGS/backend.log"; tail -5 "$LOGS/backend.log"; exit 1; }
  sleep 1
done

if [[ $LOCAL_ONLY -eq 1 ]]; then
  printf "\n  Dashboard  http://127.0.0.1:8000/api/dashboard\n  Demo       http://127.0.0.1:8000/api/demo\n\n"
  exit 0
fi

# ------------------------------------------------------------------- tunnel ---
if pgrep -f "cloudflared tunnel run" >/dev/null 2>&1; then
  echo "• tunnel already running"
else
  echo "• starting tunnel…"
  nohup cloudflared tunnel run coastal-patrol > "$LOGS/tunnel.log" 2>&1 &
fi

for i in $(seq 1 30); do
  # `grep -c` prints 0 *and* exits non-zero when there are no matches, so a
  # `|| echo 0` fallback appends a second line and breaks the comparison.
  n=$(grep -c "Registered tunnel connection" "$LOGS/tunnel.log" 2>/dev/null || true)
  n=${n:-0}
  if [[ "$n" -gt 0 ]]; then echo "  ✓ tunnel connected ($n connection(s))"; break; fi
  [[ $i -eq 30 ]] && { echo "  ✗ tunnel did not connect — see $LOGS/tunnel.log"; tail -5 "$LOGS/tunnel.log"; exit 1; }
  sleep 1
done

printf "\n  Public demo   https://coastalpatrol.app\n  Station       https://station.coastalpatrol.app\n\n"
printf "  Verify:  ./deploy/verify.sh https://coastalpatrol.app\n  Stop:    ./deploy/stop.sh\n\n"
