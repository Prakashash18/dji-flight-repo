import unittest
import os
import json
import pandas as pd
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv

# Load env variables from backend/.env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'backend', '.env'))

# Import app modules
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'processing_station'))


from georeferencer import TelemetryInterpolator
from sealion import SeaLionClient
from fastapi.testclient import TestClient
from main import app

class TestBeachLitterSystem(unittest.TestCase):
    
    def setUp(self):
        # Setup telemetry mock file
        self.mock_csv_path = 'test_telemetry.csv'
        self.telemetry_df = pd.DataFrame({
            'timestamp_ms': [0, 1000, 2000, 3000],
            'latitude': [1.2000, 1.2100, 1.2200, 1.2300],
            'longitude': [103.8000, 103.8100, 103.8200, 103.8300],
            'altitude': [10.0, 15.0, 12.0, 10.0]
        })
        self.telemetry_df.to_csv(self.mock_csv_path, index=False)
        
        # Test client for FastAPI backend
        self.client = TestClient(app)

    def tearDown(self):
        if os.path.exists(self.mock_csv_path):
            os.remove(self.mock_csv_path)

    # --- 1. Georeferencer Telemetry Tests ---
    def test_telemetry_interpolation(self):
        interpolator = TelemetryInterpolator()
        interpolator.load_from_csv(self.mock_csv_path)
        
        # Exact matching point
        loc_exact = interpolator.get_location(1000.0)
        self.assertEqual(loc_exact['latitude'], 1.2100)
        self.assertEqual(loc_exact['longitude'], 103.8100)
        self.assertEqual(loc_exact['altitude'], 15.0)
        
        # Halfway interpolation (at 1500ms)
        loc_interp = interpolator.get_location(1500.0)
        self.assertAlmostEqual(loc_interp['latitude'], 1.2150)
        self.assertAlmostEqual(loc_interp['longitude'], 103.8150)
        self.assertAlmostEqual(loc_interp['altitude'], 13.5)
        
        # Bounding limits (underflow)
        loc_under = interpolator.get_location(-500.0)
        self.assertEqual(loc_under['latitude'], 1.2000)
        
        # Bounding limits (overflow)
        loc_over = interpolator.get_location(4000.0)
        self.assertEqual(loc_over['latitude'], 1.2300)

    # --- 2. SEA-LION Translation Client Tests ---
    @patch('sealion.settings')
    async def _test_sealion_client_fallback_translation(self, mock_settings):
        # Empty API key forces mock translation fallback
        mock_settings.SEA_LION_API_KEY = ""
        client = SeaLionClient()
        
        # Translate alert text to Thai (th)
        alert_text = "New litter detected nearby. Assist if you are in the area."
        translation = await client.translate_text(alert_text, "th")
        self.assertEqual(translation, "พบขยะใหม่ในบริเวณใกล้เคียง โปรดช่วยเหลือหากคุณอยู่ในพื้นที่")
        
        # Translate text that is not in the mock dictionary to Tagalog (tl)
        unknown_text = "Clean the beach now"
        translation_unknown = await client.translate_text(unknown_text, "tl")
        self.assertEqual(translation_unknown, "[Tagalog] Clean the beach now")

    # Helper method since unittest does not run async tests directly without an runner
    def test_sealion_async_wrapper(self):
        import asyncio
        asyncio.run(self._test_sealion_client_fallback_translation())

    # --- 3. FastAPI Endpoint Tests ---
    def test_root_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "online")
        self.assertIn("supabase_configured", data)

    def test_pins_endpoint_lifecycle(self):
        # Create a mock image file
        file_payload = {
            "image": ("test_frame.jpg", b"fake-jpeg-data", "image/jpeg")
        }
        form_payload = {
            "latitude": "1.2845",
            "longitude": "103.8590",
            "confidence": "0.88"
        }
        
        # POST pin
        response = self.client.post("/api/pins", data=form_payload, files=file_payload)
        self.assertEqual(response.status_code, 201)
        res_data = response.json()
        self.assertEqual(res_data["latitude"], 1.2845)
        self.assertEqual(res_data["longitude"], 103.8590)
        self.assertEqual(res_data["confidence"], 0.88)
        self.assertEqual(res_data["status"], "detected")
        self.assertIn("image_url", res_data)
        
        # GET pins to verify it is returned
        get_response = self.client.get("/api/pins")
        self.assertEqual(get_response.status_code, 200)
        pins_list = get_response.json()
        
        # Match by ID
        matched = [p for p in pins_list if p["id"] == res_data["id"]]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["confidence"], 0.88)

    @patch('routes.sealion.translate_text')
    def test_alerts_endpoint_translation(self, mock_translate):
        # Define mock translation function to return expected mock value
        async def mock_translate_text(text, lang):
            if lang == "id":
                return "Peringatan Pembersihan Pantai! Terdeteksi konsentrasi sampah yang tinggi. Harap periksa peta Anda untuk pembagian zona."
            return f"[{lang}] {text}"
            
        mock_translate.side_effect = mock_translate_text

        alert_payload = {
            "title": "Storm Cleanup Campaign",
            "message": "Beach Cleanup Alert! High concentration of litter detected. Please check your map for zone assignments."
        }
        
        response = self.client.post("/api/alerts/broadcast", json=alert_payload)
        self.assertEqual(response.status_code, 201)
        res_data = response.json()
        
        self.assertEqual(res_data["title"], "Storm Cleanup Campaign")
        self.assertIn("translations", res_data)
        
        # Verify that translation mappings for SEA languages exist
        translations = res_data["translations"]
        self.assertIn("th", translations)
        self.assertIn("id", translations)
        self.assertIn("tl", translations)
        self.assertEqual(translations["id"], "Peringatan Pembersihan Pantai! Terdeteksi konsentrasi sampah yang tinggi. Harap periksa peta Anda untuk pembagian zona.")

    @patch('processing_task.start_processing_task')
    def test_process_endpoint_custom_model(self, mock_start_task):
        mock_start_task.return_value = "mock-task-id-custom"
        
        file_payload = {
            "video": ("video.mp4", b"fake-video-bytes", "video/mp4"),
            "telemetry": ("telemetry.csv", b"timestamp_ms,latitude,longitude,altitude\n0,1.2000,103.8000,10.0", "text/csv"),
            "custom_model": ("custom_weights.pt", b"fake-pt-bytes", "application/octet-stream")
        }
        form_payload = {
            "model_name": "custom",
            "interval_ms": "1000",
            "min_confidence": "0.35"
        }
        response = self.client.post("/api/process", data=form_payload, files=file_payload)
        self.assertEqual(response.status_code, 200)
        res_data = response.json()
        self.assertEqual(res_data["status"], "pending")
        self.assertEqual(res_data["task_id"], "mock-task-id-custom")
        
        mock_start_task.assert_called_once()
        args, kwargs = mock_start_task.call_args
        model_path = kwargs["model_path"]
        self.assertIn("temp_uploads", model_path)
        self.assertTrue(model_path.endswith("_custom_weights.pt"))
        
        # Clean up files created during test
        if os.path.exists(kwargs["video_path"]):
            os.remove(kwargs["video_path"])
        if os.path.exists(kwargs["telemetry_path"]):
            os.remove(kwargs["telemetry_path"])
        if os.path.exists(model_path):
            os.remove(model_path)

    def test_process_endpoint_custom_model_invalid_extension(self):
        file_payload = {
            "video": ("video.mp4", b"fake-video-bytes", "video/mp4"),
            "telemetry": ("telemetry.csv", b"timestamp_ms,latitude,longitude,altitude\n0,1.2000,103.8000,10.0", "text/csv"),
            "custom_model": ("invalid_weights.txt", b"fake-txt-bytes", "text/plain")
        }
        form_payload = {
            "model_name": "custom",
            "interval_ms": "1000",
            "min_confidence": "0.35"
        }
        response = self.client.post("/api/process", data=form_payload, files=file_payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Only .pt (PyTorch) model weights files are allowed.", response.json()["detail"])

    def test_telemetry_srt_bracketed_format(self):
        from georeferencer import TelemetryInterpolator as PSTelemetryInterpolator
        from georeferencing import TelemetryInterpolator as BackendTelemetryInterpolator
        
        for interp_cls in [PSTelemetryInterpolator, BackendTelemetryInterpolator]:
            interpolator = interp_cls()
            temp_srt = 'test_telemetry_bracketed.srt'
            srt_content = (
                "1\n"
                "00:00:00,000 --> 00:00:01,000\n"
                "[latitude : 1.3521] [longtitude : 103.8198] [altitude: 15.2] [heading: 45.0]\n"
            )
            with open(temp_srt, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            try:
                interpolator.load_from_srt(temp_srt)
                self.assertEqual(len(interpolator.telemetry_data), 1)
                state = interpolator.get_location(500)
                self.assertAlmostEqual(state['latitude'], 1.3521)
                self.assertAlmostEqual(state['longitude'], 103.8198)
                self.assertAlmostEqual(state['altitude'], 15.2)
                if hasattr(interpolator.telemetry_data, 'heading') or 'heading' in state:
                    self.assertAlmostEqual(state['heading'], 45.0)
            finally:
                if os.path.exists(temp_srt):
                    os.remove(temp_srt)

    def test_telemetry_srt_positional_format(self):
        from georeferencer import TelemetryInterpolator as PSTelemetryInterpolator
        from georeferencing import TelemetryInterpolator as BackendTelemetryInterpolator
        
        for interp_cls in [PSTelemetryInterpolator, BackendTelemetryInterpolator]:
            interpolator = interp_cls()
            temp_srt = 'test_telemetry_positional.srt'
            
            # Test Case A: GPS(lon, lat, alt) - Singapore context where lon is ~103
            srt_content_a = (
                "1\n"
                "00:00:00,000 --> 00:00:01,000\n"
                "GPS(103.8198, 1.3521, 15.2) compass: 90.0\n"
            )
            
            # Test Case B: GPS(lat, lon, alt) - Stockholm context where lat is ~59
            srt_content_b = (
                "1\n"
                "00:00:00,000 --> 00:00:01,000\n"
                "GPS(59.3023, 18.2030, 132.8) heading: 180.0\n"
            )
            
            with open(temp_srt, 'w', encoding='utf-8') as f:
                f.write(srt_content_a)
            try:
                interpolator.load_from_srt(temp_srt)
                state = interpolator.get_location(0)
                self.assertAlmostEqual(state['latitude'], 1.3521)
                self.assertAlmostEqual(state['longitude'], 103.8198)
                self.assertAlmostEqual(state['altitude'], 15.2)
                if 'heading' in state:
                    self.assertAlmostEqual(state['heading'], 90.0)
            finally:
                if os.path.exists(temp_srt):
                    os.remove(temp_srt)
                    
            with open(temp_srt, 'w', encoding='utf-8') as f:
                f.write(srt_content_b)
            try:
                interpolator.load_from_srt(temp_srt)
                state = interpolator.get_location(0)
                self.assertAlmostEqual(state['latitude'], 59.3023)
                self.assertAlmostEqual(state['longitude'], 18.2030)
                self.assertAlmostEqual(state['altitude'], 132.8)
                if 'heading' in state:
                    self.assertAlmostEqual(state['heading'], 180.0)
            finally:
                if os.path.exists(temp_srt):
                    os.remove(temp_srt)

if __name__ == '__main__':
    unittest.main()
