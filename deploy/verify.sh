#!/usr/bin/env bash
# Verifies a Coastal Patrol deployment.
#
#   ./deploy/verify.sh                                  # local, before deploying
#   ./deploy/verify.sh https://coastalpatrol.app        # public hostname
#   ./deploy/verify.sh https://station.coastalpatrol.app --station
#
# Local mode checks the app itself. Public mode additionally checks that the
# tunnel allowlist is blocking what it should and that Cloudflare is caching.

set -uo pipefail

BASE="${1:-http://127.0.0.1:8000}"
MODE="${2:-}"
PUBLIC=0
[[ "$BASE" == https://* ]] && PUBLIC=1
STATION=0
[[ "$MODE" == "--station" ]] && STATION=1

pass=0; fail=0; warn=0
ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; pass=$((pass+1)); }
bad()  { printf "  \033[31m✗\033[0m %s\n" "$1"; fail=$((fail+1)); }
note() { printf "  \033[33m!\033[0m %s\n" "$1"; warn=$((warn+1)); }

code() { curl -s -o /dev/null -m 20 -w "%{http_code}" "$1" 2>/dev/null; }
hdr()  { curl -s -o /dev/null -m 20 -D - "$1" 2>/dev/null | grep -i "^$2:" | tr -d '\r' | cut -d' ' -f2-; }

echo
echo "Verifying $BASE"
echo "─────────────────────────────────────────────────────────────"

# ---------------------------------------------------------------- reachable ---
echo "Demo surface"
for p in /api/demo /api/live /api/demo/data; do
  c=$(code "$BASE$p")
  [[ "$c" == "200" ]] && ok "$p → 200" || bad "$p → $c (expected 200)"
done

c=$(code "$BASE/static/vendor/leaflet.js")
[[ "$c" == "200" ]] && ok "vendored leaflet served locally" || bad "vendored leaflet → $c"

cc=$(hdr "$BASE/static/vendor/leaflet.js" "cache-control")
[[ "$cc" == *immutable* ]] && ok "vendor assets marked immutable" || bad "vendor Cache-Control: ${cc:-none}"

cc=$(hdr "$BASE/api/live" "cache-control")
[[ "$cc" == *max-age=2* ]] && ok "live feed micro-cacheable ($cc)" || bad "live Cache-Control: ${cc:-none}"

# ------------------------------------------------------------------- proxies ---
echo
echo "Proxies (no third-party fetches from the browser)"
c=$(code "$BASE/api/tiles/sat/16/51894/33813")
[[ "$c" == "200" ]] && ok "tile proxy → 200" || bad "tile proxy → $c"
for bad_tile in "sat/99/1/1" "evil/16/1/1"; do
  c=$(code "$BASE/api/tiles/$bad_tile")
  [[ "$c" == "404" ]] && ok "tile abuse rejected ($bad_tile)" || bad "tile $bad_tile → $c (expected 404)"
done
c=$(code "$BASE/api/crops/../../../etc/passwd")
[[ "$c" == "404" ]] && ok "crop path traversal rejected" || bad "crop traversal → $c (expected 404)"

# Confirm the demo payload points at our own origin, not Supabase/Esri.
ext=$(curl -s -m 25 "$BASE/api/demo/data" 2>/dev/null \
      | grep -o '"image_url": *"[^"]*"' | grep -c 'supabase\|storage.googleapis' || true)
[[ "${ext:-0}" == "0" ]] && ok "crop URLs served from our origin" \
                         || bad "$ext crop URLs still point off-origin"

# -------------------------------------------------------------- public only ---
if [[ $PUBLIC -eq 1 && $STATION -eq 0 ]]; then
  echo
  echo "Allowlist — these must NOT be reachable publicly"
  for p in /api/process /api/dashboard /api/pins /api/missions /api/profiles \
           /api/zones /api/alerts/broadcast /api/export/summary /docs /openapi.json; do
    c=$(code "$BASE$p")
    [[ "$c" == "404" ]] && ok "$p → 404" || bad "$p → $c  ← REACHABLE, fix ingress"
  done

  echo
  echo "Cloudflare caching"
  for p in /static/vendor/leaflet.js /static/sample_preview.mp4 \
           /api/tiles/sat/16/51894/33813.jpg /api/live; do
    curl -s -o /dev/null -m 25 "$BASE$p"          # prime
    st=$(hdr "$BASE$p" "cf-cache-status")
    case "${st:-none}" in
      HIT)     ok "$p cached at edge (HIT)" ;;
      MISS|EXPIRED|REVALIDATED) note "$p → $st (retry; may need a moment)" ;;
      DYNAMIC) bad "$p → DYNAMIC  ← Cache Rule not matching" ;;
      *)       bad "$p → ${st:-no CF header}  ← not behind Cloudflare?" ;;
    esac
  done

  echo
  echo "Bare domain"
  # Must ask as a browser would: the redirect is deliberately only for HTML
  # clients, so plain curl gets the JSON status endpoint instead.
  loc=$(curl -s -o /dev/null -m 20 -D - -H "Accept: text/html" "$BASE/" 2>/dev/null \
        | grep -i "^location:" | tr -d '\r' | cut -d' ' -f2-)
  [[ "$loc" == "/api/demo" ]] && ok "/ redirects visitors to the demo" \
                              || bad "/ → ${loc:-no redirect} (expected /api/demo)"
fi

# ------------------------------------------------------------- station only ---
if [[ $STATION -eq 1 ]]; then
  echo
  echo "Station hostname"
  c=$(code "$BASE/api/dashboard")
  cfa=$(hdr "$BASE/api/dashboard" "cf-access-domain")
  loc=$(hdr "$BASE/api/dashboard" "location")
  if [[ -n "$cfa" || "$loc" == *cloudflareaccess* ]]; then
    ok "dashboard is behind Cloudflare Access"
  elif [[ "$c" == "200" ]]; then
    bad "dashboard returns 200 with NO Access policy ← anyone can reach /api/process"
  else
    note "dashboard → $c (unexpected; check Access config)"
  fi
fi

# ----------------------------------------------------------------- summary ---
echo
echo "─────────────────────────────────────────────────────────────"
printf "  %d passed, %d failed, %d to re-check\n" "$pass" "$fail" "$warn"
[[ $PUBLIC -eq 0 ]] && echo "  (local mode — allowlist and caching are enforced by Cloudflare, test after deploy)"
echo
exit $(( fail > 0 ? 1 : 0 ))
