import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(dotenv_path='backend/.env')
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

supabase = create_client(url, key)

res = supabase.table("profiles").select("*").execute()
print("Profiles in DB:", res.data)
