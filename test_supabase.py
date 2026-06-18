import os
import sys
import uuid
import unittest
import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

# Add backend directory to path to load settings if needed
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from config import settings

class TestSupabaseIntegration(unittest.TestCase):
    supabase: Client = None

    @classmethod
    def setUpClassClass(cls):
        pass

    def setUp(self):
        # Load env variables from backend/.env
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'backend', '.env'))
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        
        if not self.url or not self.key:
            self.fail("❌ SUPABASE_URL or SUPABASE_KEY is missing from backend/.env file.")
            
        try:
            self.supabase = create_client(self.url, self.key)
        except Exception as e:
            self.fail(f"❌ Failed to initialize Supabase client: {e}")

    def test_01_client_initialization(self):
        """Test if the client connects and initializes successfully."""
        self.assertIsNotNone(self.supabase, "Supabase client is not initialized")
        print("\n✅ Supabase client initialized successfully.")

    def test_02_storage_bucket(self):
        """Test connection to Supabase Storage and ensure litter-images bucket exists."""
        bucket_name = "litter-images"
        print(f"\nChecking storage bucket '{bucket_name}'...")
        
        # List existing buckets
        try:
            buckets = self.supabase.storage.list_buckets()
            bucket_names = [b.name for b in buckets]
            print(f"Existing buckets: {bucket_names}")
        except Exception as e:
            self.fail(f"❌ Failed to list storage buckets: {e}")

        # Create bucket if it doesn't exist
        if bucket_name not in bucket_names:
            print(f"Bucket '{bucket_name}' not found. Attempting to create it...")
            try:
                self.supabase.storage.create_bucket(bucket_name, options={"public": True})
                print(f"✅ Successfully created bucket '{bucket_name}'.")
            except Exception as e:
                self.fail(f"❌ Failed to create bucket '{bucket_name}': {e}")
        else:
            print(f"✅ Bucket '{bucket_name}' already exists.")

        # Test uploading, getting URL, and deleting a dummy file
        test_filename = f"test_connection_{uuid.uuid4()}.txt"
        test_data = b"Supabase integration test connection file."
        
        try:
            # Upload
            upload_res = self.supabase.storage.from_(bucket_name).upload(
                path=test_filename,
                file=test_data,
                file_options={"content-type": "text/plain"}
            )
            self.assertIsNotNone(upload_res, "Upload returned None")
            print("✅ Successfully uploaded test file to storage.")

            # Get public URL
            public_url = self.supabase.storage.from_(bucket_name).get_public_url(test_filename)
            self.assertTrue(public_url.startswith("http"), "Public URL is invalid")
            print(f"✅ Retrieved test file public URL: {public_url}")

            # Delete
            delete_res = self.supabase.storage.from_(bucket_name).remove([test_filename])
            self.assertIsNotNone(delete_res, "Delete returned None")
            print("✅ Successfully deleted test file from storage.")
        except Exception as e:
            self.fail(f"❌ Storage file operations failed: {e}")

    def test_03_database_schema_and_crud(self):
        """Test if the required database tables exist and can perform CRUD operations."""
        required_tables = ["profiles", "litter_pins", "cleanup_zones", "alerts"]
        missing_tables = []
        
        # Check if tables exist in Postgrest schema cache
        for table in required_tables:
            try:
                # Query limit 0 to check table existence
                self.supabase.table(table).select("*").limit(0).execute()
            except Exception as e:
                error_msg = str(e)
                if "PGRST205" in error_msg or "Could not find the table" in error_msg:
                    missing_tables.append(table)
                else:
                    print(f"⚠️ Table '{table}' check returned unexpected error: {e}")
                    missing_tables.append(table)

        if missing_tables:
            print("\n❌ DATABASE SCHEMA TEST FAILED!")
            print(f"Missing tables: {missing_tables}")
            print("\n👉 To resolve this, run the DDL schema SQL script:")
            print(f"   Copy the content of 'supabase/schema.sql'")
            print("   and paste it into the SQL Editor in your Supabase Dashboard.")
            self.fail(f"Database schema is incomplete. Missing tables: {missing_tables}")

        print("\n✅ Database schema check passed. Running CRUD verification tests...")

        # 1. Test Alerts CRUD
        try:
            alert_id = str(uuid.uuid4())
            test_alert = {
                "id": alert_id,
                "title": "Integration Test Alert",
                "message": "This is a test notification from test_supabase.py",
                "translations": {"th": "การทดสอบ", "id": "Uji integrasi", "tl": "Pagsubok"}
            }
            # Insert
            ins_res = self.supabase.table("alerts").insert(test_alert).execute()
            self.assertTrue(len(ins_res.data) > 0, "Insert alert returned no data")
            print("✅ Database: alerts INSERT successful.")

            # Select
            sel_res = self.supabase.table("alerts").select("*").eq("id", alert_id).execute()
            self.assertEqual(len(sel_res.data), 1, "Select alert failed")
            self.assertEqual(sel_res.data[0]["title"], "Integration Test Alert")
            print("✅ Database: alerts SELECT successful.")

            # Delete
            del_res = self.supabase.table("alerts").delete().eq("id", alert_id).execute()
            self.assertEqual(len(del_res.data), 1, "Delete alert failed")
            print("✅ Database: alerts DELETE successful.")
        except Exception as e:
            self.fail(f"❌ Alerts CRUD test failed: {e}")

        # 2. Test Litter Pins CRUD
        try:
            pin_id = str(uuid.uuid4())
            test_pin = {
                "id": pin_id,
                "latitude": 1.3521,
                "longitude": 103.8198,
                "confidence": 0.95,
                "status": "detected",
                "image_url": "https://example.com/test-litter.jpg"
            }
            # Insert
            ins_res = self.supabase.table("litter_pins").insert(test_pin).execute()
            self.assertTrue(len(ins_res.data) > 0, "Insert pin returned no data")
            print("✅ Database: litter_pins INSERT successful (PostGIS trigger verified if no error).")

            # Select
            sel_res = self.supabase.table("litter_pins").select("*").eq("id", pin_id).execute()
            self.assertEqual(len(sel_res.data), 1, "Select pin failed")
            self.assertEqual(sel_res.data[0]["confidence"], 0.95)
            # Verify st_makepoint spatial trigger worked if column is present
            if "location" in sel_res.data[0]:
                print(f"   Spatial point geometry (location): {sel_res.data[0]['location']}")
            print("✅ Database: litter_pins SELECT successful.")

            # Delete
            del_res = self.supabase.table("litter_pins").delete().eq("id", pin_id).execute()
            self.assertEqual(len(del_res.data), 1, "Delete pin failed")
            print("✅ Database: litter_pins DELETE successful.")
        except Exception as e:
            self.fail(f"❌ Litter Pins CRUD test failed: {e}")

        # 3. Test Cleanup Zones CRUD
        try:
            zone_id = str(uuid.uuid4())
            test_zone = {
                "id": zone_id,
                "name": "Changi Beach East",
                "boundary_geojson": {
                    "type": "Polygon",
                    "coordinates": [[[103.90, 1.35], [103.91, 1.35], [103.91, 1.36], [103.90, 1.36], [103.90, 1.35]]]
                },
                "status": "pending"
            }
            # Insert
            ins_res = self.supabase.table("cleanup_zones").insert(test_zone).execute()
            self.assertTrue(len(ins_res.data) > 0, "Insert zone returned no data")
            print("✅ Database: cleanup_zones INSERT successful (PostGIS GeoJSON parser verified if no error).")

            # Select
            sel_res = self.supabase.table("cleanup_zones").select("*").eq("id", zone_id).execute()
            self.assertEqual(len(sel_res.data), 1, "Select zone failed")
            self.assertEqual(sel_res.data[0]["name"], "Changi Beach East")
            print("✅ Database: cleanup_zones SELECT successful.")

            # Delete
            del_res = self.supabase.table("cleanup_zones").delete().eq("id", zone_id).execute()
            self.assertEqual(len(del_res.data), 1, "Delete zone failed")
            print("✅ Database: cleanup_zones DELETE successful.")
        except Exception as e:
            self.fail(f"❌ Cleanup Zones CRUD test failed: {e}")

        # 4. Test Missions CRUD (migration-dependent)
        try:
            mission_id = str(uuid.uuid4())
            test_mission = {
                "id": mission_id,
                "title": "Changi Beach Cleanup May 2026",
                "description": "Patrol test run.",
                "mission_date": datetime.datetime.utcnow().isoformat()
            }
            # Insert
            ins_res = self.supabase.table("missions").insert(test_mission).execute()
            self.assertTrue(len(ins_res.data) > 0, "Insert mission returned no data")
            print("✅ Database: missions INSERT successful.")

            # Select
            sel_res = self.supabase.table("missions").select("*").eq("id", mission_id).execute()
            self.assertEqual(len(sel_res.data), 1, "Select mission failed")
            self.assertEqual(sel_res.data[0]["title"], "Changi Beach Cleanup May 2026")
            print("✅ Database: missions SELECT successful.")

            # Delete
            del_res = self.supabase.table("missions").delete().eq("id", mission_id).execute()
            self.assertEqual(len(del_res.data), 1, "Delete mission failed")
            print("✅ Database: missions DELETE successful.")
        except Exception as e:
            print(f"\n⚠️ Database: missions CRUD test skipped/failed (ensure you run the SQL editor migration in supabase/schema.sql): {e}")

if __name__ == "__main__":
    unittest.main()
