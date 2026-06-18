import os
import asyncio
from dotenv import load_dotenv

# Add backend directory to sys.path so we can import sealion
import sys
sys.path.append('backend')
from sealion import SeaLionClient

async def main():
    load_dotenv(dotenv_path='backend/.env')
    client = SeaLionClient()
    
    text = "Beach Cleanup Alert! High concentration of litter detected. Please check your map for zone assignments."
    print("API Key configured:", bool(client.api_key))
    print("API URL configured:", client.api_url)
    
    for lang in ["th", "id", "tl", "ms", "ta"]:
        res = await client.translate_text(text, lang)
        print(f"Lang: {lang} -> Result: '{res}'")

if __name__ == '__main__':
    asyncio.run(main())
