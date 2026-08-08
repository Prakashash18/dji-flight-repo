# Deploying Coastal Patrol on RunPod

A backup for the Jetson, or the primary if you'd rather not fight JetPack.
Unlike the Jetson, this is an ordinary x86 machine with an ordinary NVIDIA card,
so the normal `requirements.txt` just works.

**Read this first:** the live feed lives in the server's memory. A backup pod
cannot take over a flight already running on another machine — it has never seen
that mission, and phones will drop back to the pinned replay. Plan for *"the
Jetson won't start, run the whole demo here instead"*, not *"seamless failover
mid-flight"*.

---

## 1. Pick the pod

| setting | value | why |
|---|---|---|
| GPU | **RTX PRO 4500** ($0.72/hr, High availability) | 32 GB, 8 vCPU; the workload is many small 512px tiles, not one big model |
| Template | **Runpod Pytorch 2.8.0** (`cu1281-torch280`) | **required** — see below |
| avoid | A100 / H100 / B200 | 3-9x the price, no benefit for a 19 MB model |
| vCPU | 8+ | 4K H.265 decode, not inference, is the likely bottleneck |
| RAM | 30 GB+ | measured peak is 981 MB, so this is roomy |
| Disk | 30 GB | torch ~2.5 GB + sample 486 MB + headroom |
| Tier | **Secure Cloud** | community/spot can be reclaimed at 15s notice |

### The template must match the card

The RTX PRO 4500 is **Blackwell, compute capability sm_120**. The older
templates (PyTorch 2.1 / 2.2 / 2.4, CUDA 11.8-12.4) were built for sm_90 and
below. Pair one of those with this card and `torch.cuda.is_available()` still
returns `True` and still reports the right device name — then the first real
kernel throws `no kernel image is available for execution on the device`, or it
silently falls back to CPU at roughly 1/20th the speed.

So: **Runpod Pytorch 2.8.0** (CUDA 12.8.1), which is the CUDA generation that
added Blackwell. Step 2 below proves it rather than trusting it.

Pre-Blackwell alternatives, if you would rather not depend on this at all:
**A40** ($0.44/hr, 9 vCPU, Ampere sm_86) or **L40S** ($0.99/hr, 16 vCPU, Ada
sm_89). Both work with *any* template on that page.

Expose **HTTP port 8000**. RunPod gives the pod a public
`https://<pod-id>-8000.proxy.runpod.net` URL.

## 2. Get the code on

```bash
cd /workspace
git clone https://github.com/Prakashash18/dji-flight-repo.git coastal-patrol
cd coastal-patrol
```

The repo is ~4 MB. The weights and the sample video are deliberately not in it.

## 3. Secrets

Set these as **RunPod environment variables** (Pod → Edit → Environment), never
in Drive or the repo:

```
SUPABASE_URL, SUPABASE_KEY, SEA_LION_API_KEY, DEMO_MISSION_ID
HOST=0.0.0.0
PORT=8000
```

Then write them into the file the app reads:

```bash
cd /workspace/coastal-patrol/backend
cat > .env <<EOF
HOST=0.0.0.0
PORT=8000
SUPABASE_URL=$SUPABASE_URL
SUPABASE_KEY=$SUPABASE_KEY
SEA_LION_API_KEY=$SEA_LION_API_KEY
DEMO_MISSION_ID=$DEMO_MISSION_ID
EOF
```

## 4. Dependencies

```bash
cd /workspace/coastal-patrol/backend
python -m venv --system-site-packages venv
./venv/bin/pip install -r requirements.txt
```

`--system-site-packages` reuses the template's torch instead of downloading
another 2.5 GB. Confirm the GPU is actually visible — if this says `False`,
everything below still runs, just ~20x slower:

```bash
./venv/bin/python -c "import torch; print('cuda:', torch.cuda.is_available())"
```

## 5. Fetch the big files

Edit `deploy/assets.env` with your Drive URLs once, then:

```bash
cd /workspace/coastal-patrol && ./deploy/fetch-assets.sh
```

Pulls the weights (19 MB) and sample footage (486 MB). Skips whatever is already
there, so it is safe to re-run. If Drive throttles the video the script says so
rather than leaving you a broken file — host the `.mp4` in your Supabase bucket
and use that URL instead.

## 6. Start it

```bash
cd /workspace/coastal-patrol/backend
HOST=0.0.0.0 ./venv/bin/python main.py
```

Check both pages on the RunPod proxy URL:

- `https://<pod>-8000.proxy.runpod.net/api/dashboard` — the station
- `https://<pod>-8000.proxy.runpod.net/api/demo` — the phone view

Run the bundled sample once and read the real throughput off the **inference**
stage (`N tiles in Ns`). On an M-series Mac that is `2760 tiles in 74.8s`
= 0.61 frames/s at 4K. Compare before you plan the demo around it.

## 7. Point your domain at it

This is why the domain was worth buying: the QR code encodes
`coastalpatrol.app`, not a machine. Repoint it and every phone that already
scanned keeps working — no reprinting, no asking 500 people to rescan.

Either run `cloudflared` inside the pod with the existing
`deploy/cloudflared-config.yml`, or point a Cloudflare CNAME at the RunPod
proxy hostname. Allow a few minutes to take effect.

## 8. Save a template

Once it all works: **stop the pod and save it as a template.** Next cold start
skips the pip install and the asset download entirely — the difference between
a two-minute start and a twenty-minute one while an audience waits.

---

## Costs

Demo day is maybe 6 hours. At roughly $0.50/hr that is about **$3**; with
testing, under $20 for the trip. Vast.ai is cheaper (~$0.09-0.59/hr for a 4090)
but sells interruptible spot capacity — the wrong trade behind a live audience.
Test there if you like, run the event on Secure Cloud.

## Housekeeping between runs

```bash
rm -f backend/temp_uploads/*      # the worker does not always delete its inputs
du -sh backend/frame_cache        # ~2 MB per flight
```
