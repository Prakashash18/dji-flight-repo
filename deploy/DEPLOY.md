# Deploying Coastal Patrol on `coastalpatrol.app`

Two hostnames on one tunnel, pointing at one local server:

| Hostname | Who | Protection |
|---|---|---|
| `coastalpatrol.app` | The audience — phone demo | Public, allowlisted paths only |
| `station.coastalpatrol.app` | You — processing station | Cloudflare Access login |

Steps 1–4 (account, domain, `tunnel login`, `tunnel create`) are done in your
browser and shell. Everything below assumes the tunnel exists.

---

## 5. Route both hostnames at the tunnel

```bash
cloudflared tunnel route dns coastal-patrol coastalpatrol.app
cloudflared tunnel route dns coastal-patrol station.coastalpatrol.app
```

## 6. Install the config

```bash
cloudflared tunnel list          # copy the ID for coastal-patrol
```

Copy `deploy/cloudflared-config.yml` to `~/.cloudflared/config.yml` and replace
both `<TUNNEL_ID>` placeholders with that ID.

```bash
cp deploy/cloudflared-config.yml ~/.cloudflared/config.yml
# then edit ~/.cloudflared/config.yml
```

## 7. Start the backend, then the tunnel

```bash
cd backend && HOST=0.0.0.0 ./venv/bin/python main.py
```

```bash
cloudflared tunnel run coastal-patrol
```

`protocol: http2` is already in the config. Keep it — this network blocks
UDP/443, so QUIC never connects and cloudflared serves 530s while retrying.

Check both hostnames:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://coastalpatrol.app/api/demo          # 200
curl -s -o /dev/null -w "%{http_code}\n" https://coastalpatrol.app/api/process        # 404 (blocked at the edge)
curl -s -o /dev/null -w "%{http_code}\n" https://station.coastalpatrol.app/api/dashboard  # 200, then 302 once Access is on
```

## 8. Cache Rules — the step that makes the CDN work

Dashboard → **Caching → Cache Rules → Create rule**.

Without this, tile and crop responses are not cached: Cloudflare's default
caching keys off file extension, and `/api/tiles/sat/16/51894/33813` has none.
A quick tunnel gave `CF-Cache-Status: DYNAMIC` on *everything*, which is why a
real zone matters.

**Rule 1 — "Cache demo assets"**

- If: `(http.request.uri.path contains "/api/tiles/") or (http.request.uri.path contains "/api/crops/") or (starts_with(http.request.uri.path, "/static/"))`
- Then: **Eligible for cache**, Edge TTL **Respect origin**, Browser TTL **Respect origin**

The origin already sends the right `Cache-Control` (`immutable` for
`/static/vendor/*`, a week for crops, a year for tiles).

**Rule 2 — "Micro-cache live feed"**

- If: `http.request.uri.path eq "/api/live"`
- Then: **Eligible for cache**, Edge TTL **Respect origin** (origin sends 2s)
- Cache key: include **query string** — the cursor is what makes watchers share
  an entry.

Every caught-up phone sends the same `since`/`pins_since`, so 250 req/s from 500
phones collapses to one or two at origin.

**Verify:**

```bash
for p in /static/vendor/leaflet.js /api/tiles/sat/16/51894/33813 /api/live; do
  curl -sI "https://coastalpatrol.app$p" | grep -i cf-cache-status
done
```

First request `MISS`, second `HIT`. If it stays `DYNAMIC`, the rule is not
matching.

## 9. Access — lock the station

Zero Trust → **Access → Applications → Add a self-hosted application**.

- Application domain: `station.coastalpatrol.app`
- Policy: Allow → **Emails** → your address
- Session duration: whatever suits you

Add nothing for `coastalpatrol.app` — it stays public, and the tunnel's
allowlist is what keeps the dangerous endpoints off it.

**Verify in a private window:** `station.coastalpatrol.app` should show a
Cloudflare login, and `coastalpatrol.app/api/process` should 404.

---

## Before the event

```bash
# Warm the tile cache for the patrol area (~90 tiles, a few seconds)
# and the crop cache, so the first visitor is not the one paying.
curl -s https://coastalpatrol.app/api/demo/data > /dev/null
```

Then load `https://coastalpatrol.app/api/demo` on a phone once, pan the map, and
open Finds — that pulls the tiles and crops through and leaves them cached at the
edge.

Print the QR from the dashboard's **Share demo** button, on
`station.coastalpatrol.app` so it encodes the public hostname.

## Known limits

- **One mission at a time.** Concurrent runs deadlock the worker pool; a frame
  timeout breaks a stuck run loose after 180s but does not make it safe.
- **`/api/live` reads in-memory state.** All phones must reach the same process,
  so do not run more than one backend instance.
- **A backend restart drops the live feed's active mission.** It degrades to the
  pinned demo rather than erroring.
- **Models come only from `backend/models/`.** There is no upload and no URL
  parameter: a `.pt` is pickled Python, so a caller who can supply the bytes can
  run code. Install one with
  `python -m model_source install <drive-url> beach_litter.pt`, list them with
  `python -m model_source list`.
- **Still unfixed:** the path traversal on *video/telemetry* upload filenames.
  Reachable by anyone who gets through Access on the station.
