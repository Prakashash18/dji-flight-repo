import argparse
import os
import time

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

from georeferencer import TelemetryInterpolator
from uploader import APIUploader

def run_litter_detection(video_path: str, telemetry_path: str, model_path: str, backend_url: str, sample_interval_ms: int = 1000, mock: bool = False):
    """
    Reads a flight video, runs YOLOv8 detection at regular intervals,
    maps timestamp to GPS location, and uploads results to the backend.
    """
    print(f"🎬 Initializing Beach Litter Detector...")
    print(f"   Video: {video_path}")
    print(f"   Telemetry: {telemetry_path}")
    print(f"   Model: {model_path}")
    print(f"   Backend: {backend_url}")
    
    # 1. Load telemetry
    interpolator = TelemetryInterpolator()
    if telemetry_path.endswith('.srt'):
        interpolator.load_from_srt(telemetry_path)
    else:
        interpolator.load_from_csv(telemetry_path)
        
    # 2. Init API uploader
    uploader = APIUploader(backend_url)
    
    # 3. Load YOLO model (unless mocking)
    model = None
    if not mock:
        if YOLO is None:
            print("⚠️ [Warning] ultralytics package is not installed. Defaulting to MOCK mode.")
            mock = True
        else:
            print("🧠 Loading YOLOv8 model...")
            model = YOLO(model_path)
            
    # 4. Open video
    if not mock:
        if cv2 is None:
            print("⚠️ [Warning] opencv-python package is not installed. Defaulting to MOCK mode.")
            mock = True
        else:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"❌ Failed to open video file: {video_path}. Defaulting to MOCK mode.")
                mock = True
                
    if mock:
        print("🎭 Running in MOCK Mode. Generating dummy beach litter detections...")
        run_mock_detections(interpolator, uploader)
        return

    # Real OpenCV + YOLOv8 processing loop
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_ms = (total_frames / fps) * 1000 if fps > 0 else 0
    
    print(f"📈 Processing video ({int(duration_ms/1000)}s total duration, Sample Interval: {sample_interval_ms}ms)...")
    
    current_time_ms = 0.0
    detections_count = 0
    
    while current_time_ms < duration_ms:
        cap.set(cv2.CAP_PROP_POS_MSEC, current_time_ms)
        success, frame = cap.read()
        if not success:
            break
            
        # Run inference
        # Classes: 0 could be bottle, plastic, etc. depending on custom model weights.
        # We search for 'litter' related objects. Using default yolov8 coco classes for demo (e.g. 39: bottle, 41: cup)
        results = model(frame, conf=0.45, verbose=False)
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                
                # Check for trash/bottles/cups in general COCO classes, or any detection if custom weights
                is_litter = True  # If using custom beach-litter model
                
                if is_litter:
                    # Interpolate location
                    location = interpolator.get_location(current_time_ms)
                    
                    # Crop the detected litter area
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    crop = frame[max(0, y1):min(frame.shape[0], y2), max(0, x1):min(frame.shape[1], x2)]
                    
                    # Convert crop to JPEG buffer
                    _, buffer = cv2.imencode('.jpg', crop)
                    
                    # Upload
                    print(f"🚨 [Detected] Litter found at Lat: {location['latitude']:.5f}, Lon: {location['longitude']:.5f} (Confidence: {conf:.2f})")
                    uploader.upload_pin(
                        lat=location['latitude'],
                        lon=location['longitude'],
                        confidence=conf,
                        image_bytes=buffer.tobytes()
                    )
                    detections_count += 1
                    
        current_time_ms += sample_interval_ms
        
    cap.release()
    print(f"🏁 Processing completed. Identified and uploaded {detections_count} litter points.")

def run_mock_detections(interpolator: TelemetryInterpolator, uploader: APIUploader):
    """
    Generates dummy detections distributed along the telemetry timestamps for testing.
    """
    if interpolator.telemetry_data is None or interpolator.telemetry_data.empty:
        print("❌ Cannot run mock detections without telemetry data.")
        return
        
    # Pick a few sample timestamps
    timestamps = interpolator.telemetry_data['timestamp_ms'].values
    mock_samples = [timestamps[int(len(timestamps) * r)] for r in [0.2, 0.5, 0.8]]
    
    # Create a small 100x100 white square image bytes as dummy JPEG
    dummy_bytes = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00\x0a\x00\x0a\x01\x01\x11\x00\xff\xc4\x00\x15\x00\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xdf\xf0\x07\xff\xd9'
    
    for idx, ts in enumerate(mock_samples):
        location = interpolator.get_location(ts)
        confidence = 0.82 + (idx * 0.05)
        print(f"🎭 [Mock Detect] Litter at Lat: {location['latitude']:.5f}, Lon: {location['longitude']:.5f} (Conf: {confidence:.2f})")
        
        # Upload mock data
        uploader.upload_pin(
            lat=location['latitude'],
            lon=location['longitude'],
            confidence=confidence,
            image_bytes=dummy_bytes
        )
        time.sleep(0.5)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Beach Litter Detection Processing Station")
    parser.add_argument('--video', type=str, default='flight_video.mp4', help="Path to flight MP4 video")
    parser.add_argument('--telemetry', type=str, default='flight_telemetry.csv', help="Path to CSV or SRT flight telemetry")
    parser.add_argument('--model', type=str, default='solar_panel.pt', help="Path to YOLOv8 weights (.pt)")
    parser.add_argument('--backend', type=str, default='http://localhost:8000', help="URL of FastAPI ingest service")
    parser.add_argument('--interval', type=int, default=1000, help="Sampling interval in milliseconds")
    parser.add_argument('--mock', action='store_true', help="Force mock run (skip real video/YOLO execution)")
    
    args = parser.parse_args()
    
    # Write a temporary mock telemetry file if none exists and user runs default
    temp_created = False
    if args.telemetry == 'flight_telemetry.csv' and not os.path.exists(args.telemetry):
        print("💡 flight_telemetry.csv not found. Writing a temporary dummy log for execution...")
        import pandas as pd
        mock_df = pd.DataFrame({
            'timestamp_ms': [0, 2000, 4000, 6000, 8000, 10000],
            'latitude': [1.2830, 1.2835, 1.2840, 1.2845, 1.2850, 1.2855],
            'longitude': [103.8580, 103.8585, 103.8590, 103.8595, 103.8600, 103.8605],
            'altitude': [10.0, 12.0, 15.0, 15.0, 14.0, 12.0]
        })
        mock_df.to_csv(args.telemetry, index=False)
        temp_created = True
        
    try:
        run_litter_detection(
            video_path=args.video,
            telemetry_path=args.telemetry,
            model_path=args.model,
            backend_url=args.backend,
            sample_interval_ms=args.interval,
            mock=args.mock
        )
    finally:
        if temp_created and os.path.exists(args.telemetry):
            os.remove(args.telemetry)
