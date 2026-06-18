import os
import httpx
import traceback
from dotenv import load_dotenv

load_dotenv(dotenv_path='backend/.env')
api_key = os.getenv("SEA_LION_API_KEY")
api_url = os.getenv("SEA_LION_API_URL", "https://api.sea-lion.ai/v1")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

prompt = (
    "You are a professional translator. Translate the following English text into the language with code 'th'. "
    "Respond ONLY with the direct translation. Do not include quotes, explanations, or introductory text.\n\n"
    "English text: \"Beach Cleanup Alert! High concentration of litter detected. Please check your map for zone assignments.\"\n"
    "Translation:"
)

payload = {
    "model": "aisingapore/Gemma-SEA-LION-v4-27B-IT",
    "messages": [
        {"role": "user", "content": prompt}
    ],
    "temperature": 0.1,
    "max_tokens": 200
}

try:
    print("Sending POST request to:", f"{api_url}/chat/completions")
    r = httpx.post(f"{api_url}/chat/completions", json=payload, headers=headers, timeout=12.0)
    print("Response Status Code:", r.status_code)
    print("Response Body:", r.text)
except Exception as e:
    print("Exception occurred:")
    traceback.print_exc()
