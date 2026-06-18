import requests
import json

class APIUploader:
    """
    Client utility that uploads detected litter coordinates, confidence,
    and visual evidence to the central FastAPI Backend.
    """
    def __init__(self, backend_url: str):
        self.backend_url = backend_url.rstrip('/')
        self.upload_url = f"{self.backend_url}/api/pins"

    def upload_pin(self, lat: float, lon: float, confidence: float, image_bytes: bytes) -> bool:
        """
        Sends a POST request with multipart/form-data containing the metadata and frame image.
        """
        payload = {
            "latitude": str(lat),
            "longitude": str(lon),
            "confidence": str(confidence)
        }
        
        files = {
            "image": ("litter_crop.jpg", image_bytes, "image/jpeg")
        }
        
        try:
            print(f"[APIUploader] Sending pin to {self.upload_url}...")
            response = requests.post(self.upload_url, data=payload, files=files, timeout=10)
            
            if response.status_code in (200, 201):
                res_data = response.json()
                print(f"✅ [APIUploader] Successfully uploaded pin. ID: {res_data.get('id', 'N/A')}")
                return True
            else:
                print(f"❌ [APIUploader] Server rejected upload (Status {response.status_code}): {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"⚠️ [APIUploader] HTTP Connection failure: {e}")
            return False

if __name__ == '__main__':
    # Dry-run test of uploader
    uploader = APIUploader("http://localhost:8000")
    dummy_bytes = b"fake-jpeg-data"
    uploader.upload_pin(1.290, 103.852, 0.95, dummy_bytes)
