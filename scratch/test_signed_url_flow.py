import os
import sys
import unittest
import requests
import uuid
from dotenv import load_dotenv

# Add backend directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
from main import app
from fastapi.testclient import TestClient

class TestSignedUrlUploadFlow(unittest.TestCase):
    def setUp(self):
        # Load env variables
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))
        self.client = TestClient(app)
        
        # Verify GCS client can be initialized
        try:
            from google.cloud import storage
            self.storage_client = storage.Client()
            self.bucket_name = os.getenv("GCS_BUCKET_NAME", "dji-flight-volunteer-app-assets")
        except Exception as e:
            self.skipTest(f"Google Cloud Storage credentials/client not available: {e}. Skipping integration test.")

    def test_signed_url_flow(self):
        # 1. Request signed URL from our backend
        test_filename = f"integration_test_{uuid.uuid4()}.mp4"
        print(f"\n1. Requesting signed upload URL for '{test_filename}'...")
        response = self.client.get(f"/api/process/signed-upload-url?filename={test_filename}")
        self.assertEqual(response.status_code, 200, f"Failed to get signed URL: {response.text}")
        
        data = response.json()
        self.assertIn("signed_url", data)
        self.assertIn("public_url", data)
        self.assertIn("gcs_video_path", data)
        
        signed_url = data["signed_url"]
        public_url = data["public_url"]
        storage_path = data["gcs_video_path"]
        
        print(f"👉 Signed URL received: {signed_url[:100]}...")
        print(f"👉 Public URL: {public_url}")
        print(f"👉 GCS Path: {storage_path}")
        
        # 2. Upload dummy video bytes directly to GCS signed URL using PUT
        dummy_video_content = b"fake-video-frames-data-bytes"
        print("2. Uploading dummy video file to signed URL...")
        upload_res = requests.put(
            signed_url, 
            data=dummy_video_content, 
            headers={"Content-Type": "application/octet-stream"}
        )
        self.assertEqual(upload_res.status_code, 200, f"Upload to signed URL failed: {upload_res.text}")
        print("✅ Successfully uploaded to Google Cloud Storage.")
        
        # 3. Request task processing using the uploaded GCS path
        print("3. Triggering flight processing via gcs_video_path...")
        file_payload = {
            "telemetry": ("telemetry.csv", b"timestamp_ms,latitude,longitude,altitude\n0,1.2000,103.8000,10.0", "text/csv")
        }
        
        # Resolve model path to absolute path to ensure YOLO can find it from any working directory
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
        abs_model_path = os.path.join(backend_dir, "solar_panel.pt")
        
        form_payload = {
            "gcs_video_path": storage_path,
            "model_name": abs_model_path,
            "interval_ms": "1000",
            "min_confidence": "0.35"
        }
        
        process_res = self.client.post("/api/process", data=form_payload, files=file_payload)
        self.assertEqual(process_res.status_code, 200, f"Failed to submit process task: {process_res.text}")
        process_data = process_res.json()
        self.assertEqual(process_data["status"], "pending")
        self.assertIn("task_id", process_data)
        
        task_id = process_data["task_id"]
        print(f"✅ Processing task started successfully. Task ID: {task_id}")
        
        # 4. Check status to verify it's registered
        status_res = self.client.get(f"/api/process/status/{task_id}")
        self.assertEqual(status_res.status_code, 200)
        status_data = status_res.json()
        print(f"👉 Initial status: {status_data['status']}")
        
        # 5. Wait for task to finish or fail and verify storage cleanup
        print("4. Waiting for background task to complete and cleanup...")
        import time
        max_retries = 15
        for i in range(max_retries):
            time.sleep(1.0)
            status_res = self.client.get(f"/api/process/status/{task_id}")
            status_data = status_res.json()
            if status_data["status"] in ("completed", "failed"):
                print(f"🏁 Task finished with status: {status_data['status']}")
                if status_data["status"] == "failed":
                    print(f"⚠️ Error from task: {status_data.get('error')}")
                break
        
        # Verify the file is deleted from GCS
        print("5. Checking that the video file was cleaned up from GCS...")
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(storage_path)
        self.assertFalse(blob.exists(), "File should have been cleaned up from GCS but it still exists!")
        print("✅ Verified GCS storage cleanup successfully.")

if __name__ == "__main__":
    unittest.main()
