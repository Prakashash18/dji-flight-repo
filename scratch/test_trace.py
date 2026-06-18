import os
import asyncio
import traceback
from dotenv import load_dotenv

import sys
sys.path.append('backend')
from sealion import SeaLionClient

async def main():
    load_dotenv(dotenv_path='backend/.env')
    client = SeaLionClient()
    
    text = "Beach Cleanup Alert! High concentration of litter detected. Please check your map for zone assignments."
    
    for lang in ["th", "id", "tl", "ms", "ta"]:
        print(f"Testing translation for {lang}...")
        try:
            # Replicate direct translate_text logic but with traceback
            target_lang = lang.lower().strip()
            headers = {
                "Authorization": f"Bearer {client.api_key}",
                "Content-Type": "application/json"
            }
            prompt = (
                f"You are a professional translator. Translate the following English text into the language with code '{target_lang}'. "
                f"Respond ONLY with the direct translation. Do not include quotes, explanations, or introductory text.\n\n"
                f"English text: \"{text}\"\n"
                f"Translation:"
            )
            payload = {
                "model": "aisingapore/Gemma-SEA-LION-v4-27B-IT",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 200
            }
            
            import httpx
            async with httpx.AsyncClient() as http_client:
                response = await http_client.post(
                    f"{client.api_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=12.0
                )
                print(f"Status for {lang}:", response.status_code)
                if response.status_code == 200:
                    res_json = response.json()
                    translation = res_json['choices'][0]['message']['content'].strip()
                    print(f"API Result for {lang}: '{translation}'")
                else:
                    print(f"API Error for {lang}:", response.text)
        except Exception as e:
            print(f"Failed for {lang} with exception:")
            traceback.print_exc()
        print("-" * 30)

if __name__ == '__main__':
    asyncio.run(main())
