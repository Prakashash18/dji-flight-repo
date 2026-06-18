import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(dotenv_path='backend/.env')
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

supabase = create_client(url, key)

# Try fetching one row to see its keys
res = supabase.table("litter_pins").select("*").limit(1).execute()
if res.data:
    print("Columns in litter_pins:", list(res.data[0].keys()))
else:
    print("litter_pins table is empty, fetching table details...")
    # Insert a dummy pin and rollback/delete it, or just list columns by querying a dummy query
    try:
        dummy_id = "00000000-0000-0000-0000-000000000000"
        res_ins = supabase.table("litter_pins").insert({
            "id": dummy_id,
            "latitude": 0.0,
            "longitude": 0.0,
            "status": "detected"
        }).execute()
        if res_ins.data:
            print("Columns in litter_pins from inserted dummy:", list(res_ins.data[0].keys()))
            # clean up
            supabase.table("litter_pins").delete().eq("id", dummy_id).execute()
    except Exception as e:
        print("Error checking columns:", e)
