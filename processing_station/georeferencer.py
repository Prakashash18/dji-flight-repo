import pandas as pd
import numpy as np
import os
import re

class TelemetryInterpolator:
    """
    Parses DJI drone flight logs (CSV or SRT telemetry) and interpolates GPS coordinates
    (latitude, longitude, altitude) for a given video time offset.
    """
    def __init__(self):
        self.telemetry_data = None  # DataFrame with columns: ['timestamp_ms', 'latitude', 'longitude', 'altitude']

    def load_from_csv(self, file_path: str):
        """
        Loads telemetry from a CSV file.
        Expected headers: 'timestamp_ms' (or 'time_offset_s'), 'latitude', 'longitude', 'altitude'
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Telemetry log file not found at: {file_path}")
        
        df = pd.read_csv(file_path)
        
        # Standardize columns
        df.columns = [col.strip().lower() for col in df.columns]
        
        # Handle time mapping
        if 'time_offset_s' in df.columns and 'timestamp_ms' not in df.columns:
            df['timestamp_ms'] = df['time_offset_s'] * 1000.0
            
        required_cols = {'timestamp_ms', 'latitude', 'longitude'}
        if not required_cols.issubset(set(df.columns)):
            raise ValueError(f"CSV file must contain columns: {required_cols}. Found: {df.columns.tolist()}")
            
        if 'altitude' not in df.columns:
            df['altitude'] = 0.0
            
        # Ensure sorted by timestamp
        self.telemetry_data = df[['timestamp_ms', 'latitude', 'longitude', 'altitude']].sort_values('timestamp_ms').reset_index(drop=True)
        print(f"[TelemetryInterpolator] Loaded {len(self.telemetry_data)} GPS telemetry points from CSV.")

    def load_from_srt(self, file_path: str):
        """
        Parses DJI-style subtitle (SRT) file containing telemetry embedded per frame/second.
        Example SRT entry:
        1
        00:00:01,000 --> 00:00:02,000
        [latitude: 1.3456] [longitude: 103.9871] [altitude: 45.2]
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Telemetry SRT file not found at: {file_path}")
            
        records = []
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Regex to split on SRT index numbers
        blocks = re.split(r'\n\s*\n', content.strip())
        
        for block in blocks:
            lines = block.split('\n')
            if len(lines) < 3:
                continue
                
            time_match = re.search(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})', lines[1])
            if not time_match:
                continue
                
            # Parse start time to milliseconds
            hrs, mins, secs, ms = map(int, time_match.groups()[:4])
            timestamp_ms = ((hrs * 3600) + (mins * 60) + secs) * 1000 + ms
            
            # Parse lat, lon, alt from third line onwards
            data_line = " ".join(lines[2:])
            lat_m = re.search(r'(?:latitude|lat)\s*[:\s]\s*([-\d.]+)', data_line, re.IGNORECASE)
            lon_m = re.search(r'(?:longitude|longtitude|lon|lng)\s*[:\s]\s*([-\d.]+)', data_line, re.IGNORECASE)
            alt_m = re.search(r'(?:altitude|alt|height)\s*[:\s]\s*([-\d.]+)', data_line, re.IGNORECASE)
            
            lat, lon, alt = None, None, 0.0
            
            if lat_m and lon_m:
                lat = float(lat_m.group(1))
                lon = float(lon_m.group(1))
            else:
                gps_match = re.search(r'gps\s*[:\s(]\s*([-\d.]+)\s*,\s*([-\d.]+)\s*(?:,\s*([-\d.]+))?', data_line, re.IGNORECASE)
                if gps_match:
                    val1 = float(gps_match.group(1))
                    val2 = float(gps_match.group(2))
                    val3 = float(gps_match.group(3)) if gps_match.group(3) else 0.0
                    
                    if abs(val1) > 90.0:
                        lon = val1
                        lat = val2
                    elif abs(val2) > 90.0:
                        lon = val2
                        lat = val1
                    else:
                        lat = val1
                        lon = val2
                    alt = val3
                    
            if lat is not None and lon is not None:
                if alt_m:
                    alt = float(alt_m.group(1))
                records.append({
                    'timestamp_ms': timestamp_ms,
                    'latitude': lat,
                    'longitude': lon,
                    'altitude': alt
                })
                
        if not records:
            raise ValueError("No valid GPS telemetry records found in the SRT file.")
            
        self.telemetry_data = pd.DataFrame(records).sort_values('timestamp_ms').reset_index(drop=True)
        print(f"[TelemetryInterpolator] Loaded {len(self.telemetry_data)} GPS telemetry points from SRT.")

    def get_location(self, video_timestamp_ms: float) -> dict:
        """
        Interpolates the GPS coordinate and altitude for the exact video frame timestamp (ms).
        Uses simple linear interpolation between the nearest bounding telemetry points.
        """
        if self.telemetry_data is None or self.telemetry_data.empty:
            raise ValueError("Telemetry data must be loaded before performing query.")
            
        times = self.telemetry_data['timestamp_ms'].values
        lats = self.telemetry_data['latitude'].values
        lons = self.telemetry_data['longitude'].values
        alts = self.telemetry_data['altitude'].values
        
        # Out of bounds check
        if video_timestamp_ms <= times[0]:
            return {"latitude": lats[0], "longitude": lons[0], "altitude": alts[0]}
        if video_timestamp_ms >= times[-1]:
            return {"latitude": lats[-1], "longitude": lons[-1], "altitude": alts[-1]}
            
        # Interpolate each dimension
        lat_interp = np.interp(video_timestamp_ms, times, lats)
        lon_interp = np.interp(video_timestamp_ms, times, lons)
        alt_interp = np.interp(video_timestamp_ms, times, alts)
        
        return {
            "latitude": float(lat_interp),
            "longitude": float(lon_interp),
            "altitude": float(alt_interp)
        }

# Simple test example
if __name__ == '__main__':
    # Create mock CSV telemetry for demonstration
    mock_csv_path = 'mock_flight_telemetry.csv'
    mock_df = pd.DataFrame({
        'timestamp_ms': [0, 1000, 2000, 3000, 4000, 5000],
        'latitude': [1.2830, 1.2835, 1.2840, 1.2845, 1.2850, 1.2855],
        'longitude': [103.8580, 103.8585, 103.8590, 103.8595, 103.8600, 103.8605],
        'altitude': [10.0, 12.0, 15.0, 15.0, 14.0, 12.0]
    })
    mock_df.to_csv(mock_csv_path, index=False)
    
    # Load and test
    interpolator = TelemetryInterpolator()
    interpolator.load_from_csv(mock_csv_path)
    
    # Interpolate for 2.5 seconds (2500ms)
    coords = interpolator.get_location(2500)
    print("Interpolated location at 2500ms:", coords)
    
    # Clean up mock file
    if os.path.exists(mock_csv_path):
        os.remove(mock_csv_path)
