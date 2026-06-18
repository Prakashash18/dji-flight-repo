import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(dotenv_path='backend/.env')
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

supabase = create_client(url, key)

res = supabase.table("alerts").select("*").execute()
for alert in res.data:
    print("Alert ID:", alert["id"])
    print("Title:", alert["title"])
    print("Message:", alert["message"])
    print("Translations:", alert["translations"])
    print("-" * 50)
