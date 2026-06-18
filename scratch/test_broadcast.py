import httpx
import json

url = "http://localhost:8000/api/alerts/broadcast"
payload = {
    "title": "Live Broadcast Test",
    "message": "Beach Cleanup Alert! High concentration of litter detected. Please check your map for zone assignments."
}

try:
    r = httpx.post(url, json=payload, timeout=15.0)
    print("Status Code:", r.status_code)
    print("Response JSON:")
    print(json.dumps(r.json(), indent=2, ensure_ascii=False))
except Exception as e:
    print("Error broadcasting:", e)
