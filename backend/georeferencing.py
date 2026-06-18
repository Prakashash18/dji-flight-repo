import os
import re
import math
import pandas as pd
import numpy as np

class TelemetryInterpolator:
    """
    Parses DJI drone flight logs (CSV or SRT telemetry) and interpolates GPS coordinates
    (latitude, longitude, altitude, heading) for a given video time offset.
    """
    def __init__(self):
        # DataFrame with columns: ['timestamp_ms', 'latitude', 'longitude', 'altitude', 'heading']
        self.telemetry_data = None  

    def load_from_csv(self, file_path: str):
        """
        Loads telemetry from a CSV file.
        Detects common headers and maps them to standard columns.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Telemetry log file not found at: {file_path}")
        
        df = pd.read_csv(file_path)
        
        # Standardize columns
        col_map = {col: col.strip().lower() for col in df.columns}
        df = df.rename(columns=col_map)
        
        # Handle time mapping
        timestamp_col = None
        for col in ['timestamp_ms', 'timestamp', 'time(ms)', 'time', 'time_ms']:
            if col in df.columns:
                timestamp_col = col
                break
        
        if timestamp_col:
            df['timestamp_ms_clean'] = df[timestamp_col].astype(float)
        elif 'time_offset_s' in df.columns:
            df['timestamp_ms_clean'] = df['time_offset_s'].astype(float) * 1000.0
        elif 'time(seconds)' in df.columns:
            df['timestamp_ms_clean'] = df['time(seconds)'].astype(float) * 1000.0
        else:
            # Fallback: assume rows are spaced 100ms apart (10Hz log)
            df['timestamp_ms_clean'] = np.arange(len(df)) * 100.0
            
        # Latitude
        lat_col = next((c for c in ['latitude', 'lat', 'latitude(degrees)', 'y'] if c in df.columns), None)
        if not lat_col:
            raise ValueError(f"Could not find latitude column in CSV. Available columns: {df.columns.tolist()}")
            
        # Longitude
        lon_col = next((c for c in ['longitude', 'lon', 'lng', 'longitude(degrees)', 'x'] if c in df.columns), None)
        if not lon_col:
            raise ValueError(f"Could not find longitude column in CSV. Available columns: {df.columns.tolist()}")
            
        # Altitude (convert to meters if in feet)
        alt_col = next((c for c in ['altitude', 'ascent(feet)', 'altitude(feet)', 'altitude(m)', 'height', 'height(m)'] if c in df.columns), None)
        
        # Compass Heading
        heading_col = next((c for c in ['compass_heading(degrees)', 'heading', 'bearing', 'compass', 'heading(degrees)'] if c in df.columns), None)
        
        # Build clean dataframe
        clean_records = []
        for _, row in df.iterrows():
            ts = float(row['timestamp_ms_clean'])
            lat = float(row[lat_col])
            lon = float(row[lon_col])
            
            # Altitude parsing
            alt = 0.0
            if alt_col:
                raw_alt = float(row[alt_col])
                if 'feet' in alt_col or 'ascent' in alt_col:
                    alt = raw_alt * 0.3048 # feet to meters
                else:
                    alt = raw_alt
            
            # Heading parsing
            heading = 0.0
            if heading_col:
                heading = float(row[heading_col])
                
            clean_records.append({
                'timestamp_ms': ts,
                'latitude': lat,
                'longitude': lon,
                'altitude': alt,
                'heading': heading
            })
            
        self.telemetry_data = pd.DataFrame(clean_records).sort_values('timestamp_ms').reset_index(drop=True)
        print(f"[TelemetryInterpolator] Loaded {len(self.telemetry_data)} GPS points from CSV.")

    def load_from_srt(self, file_path: str):
        """
        Parses subtitle (SRT) file containing telemetry parameters.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Telemetry SRT file not found at: {file_path}")
            
        records = []
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        blocks = re.split(r'\n\s*\n', content.strip())
        
        for block in blocks:
            lines = block.split('\n')
            if len(lines) < 3:
                continue
                
            time_match = re.search(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})', lines[1])
            if not time_match:
                continue
                
            hrs, mins, secs, ms = map(int, time_match.groups()[:4])
            timestamp_ms = ((hrs * 3600) + (mins * 60) + secs) * 1000 + ms
            
            data_line = " ".join(lines[2:])
            lat_m = re.search(r'(?:latitude|lat)\s*[:\s]\s*([-\d.]+)', data_line, re.IGNORECASE)
            lon_m = re.search(r'(?:longitude|longtitude|lon|lng)\s*[:\s]\s*([-\d.]+)', data_line, re.IGNORECASE)
            alt_m = re.search(r'(?:altitude|alt|height)\s*[:\s]\s*([-\d.]+)', data_line, re.IGNORECASE)
            heading_m = re.search(r'(?:heading|bearing|compass|compass_heading)\s*[:\s]\s*([-\d.]+)', data_line, re.IGNORECASE)
            
            lat, lon, alt, heading = None, None, 0.0, 0.0
            
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
                if heading_m:
                    heading = float(heading_m.group(1))
                    
                records.append({
                    'timestamp_ms': timestamp_ms,
                    'latitude': lat,
                    'longitude': lon,
                    'altitude': alt,
                    'heading': heading
                })
                
        if not records:
            raise ValueError("No valid GPS telemetry records found in the SRT file.")
            
        self.telemetry_data = pd.DataFrame(records).sort_values('timestamp_ms').reset_index(drop=True)
        print(f"[TelemetryInterpolator] Loaded {len(self.telemetry_data)} GPS points from SRT.")

    def get_location(self, video_timestamp_ms: float) -> dict:
        """
        Linearly interpolates drone telemetry variables at a specific video timestamp.
        """
        if self.telemetry_data is None or self.telemetry_data.empty:
            raise ValueError("Telemetry data must be loaded first.")
            
        times = self.telemetry_data['timestamp_ms'].values
        lats = self.telemetry_data['latitude'].values
        lons = self.telemetry_data['longitude'].values
        alts = self.telemetry_data['altitude'].values
        headings = self.telemetry_data['heading'].values
        
        if video_timestamp_ms <= times[0]:
            return {"latitude": lats[0], "longitude": lons[0], "altitude": alts[0], "heading": headings[0]}
        if video_timestamp_ms >= times[-1]:
            return {"latitude": lats[-1], "longitude": lons[-1], "altitude": alts[-1], "heading": headings[-1]}
            
        lat_interp = np.interp(video_timestamp_ms, times, lats)
        lon_interp = np.interp(video_timestamp_ms, times, lons)
        alt_interp = np.interp(video_timestamp_ms, times, alts)
        
        # Circular interpolation for heading
        sin_headings = np.sin(np.radians(headings))
        cos_headings = np.cos(np.radians(headings))
        sin_interp = np.interp(video_timestamp_ms, times, sin_headings)
        cos_interp = np.interp(video_timestamp_ms, times, cos_headings)
        heading_interp = math.degrees(math.atan2(sin_interp, cos_interp)) % 360
        
        return {
            "latitude": float(lat_interp),
            "longitude": float(lon_interp),
            "altitude": float(alt_interp),
            "heading": float(heading_interp)
        }

def geodesic_destination(lat: float, lon: float, distance_meters: float, bearing_degrees: float) -> tuple:
    """
    Calculates the destination coordinate (latitude, longitude) starting from a point,
    moving distance_meters along bearing_degrees (rhumb line / great circle approximation).
    """
    R = 6378137.0  # Earth's radius in meters
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    bearing_rad = math.radians(bearing_degrees)
    
    angular_dist = distance_meters / R
    
    new_lat = math.asin(
        math.sin(lat_rad) * math.cos(angular_dist) +
        math.cos(lat_rad) * math.sin(angular_dist) * math.cos(bearing_rad)
    )
    new_lon = lon_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(angular_dist) * math.cos(lat_rad),
        math.cos(angular_dist) - math.sin(lat_rad) * math.sin(new_lat)
    )
    
    return math.degrees(new_lat), math.degrees(new_lon)

def georeference_box(
    x_center: float, 
    y_center: float, 
    frame_width: int, 
    frame_height: int,
    drone_lat: float, 
    drone_lon: float, 
    drone_alt: float, 
    drone_heading: float,
    fov_degrees: float = 59.0
) -> tuple:
    """
    Converts pixel offset coordinates inside a video frame to real-world GPS coordinates (latitude, longitude)
    using the georeferencing math from Roboflow's dji-aerial-georeferencing.
    
    Parameters:
      x_center, y_center: The center point of the object bounding box (pixels).
      frame_width, frame_height: Frame size (pixels).
      drone_lat, drone_lon: Drone's interpolated GPS position.
      drone_alt: Drone's altitude in meters.
      drone_heading: Drone's heading/compass heading in degrees.
      fov_degrees: Camera diagonal field of view in degrees (default 59.0).
    """
    # 1. Normalize coordinates so center of frame is (0,0)
    # y-axis is inverted: down in pixels is positive, so we use y_center - frame_height / 2
    norm_y = y_center - (frame_height / 2)
    norm_x = x_center - (frame_width / 2)
    
    # 2. Camera Field of View math
    fov_rad = math.radians(fov_degrees)
    fov_atan = math.tan(fov_rad)
    
    # 3. Ground diagonal distance covered by FOV
    diagonal_distance = drone_alt * fov_atan
    
    # 4. Target distance in pixels vs frame diagonal
    distance_pixels = math.sqrt((frame_width / 2 - x_center) ** 2 + (frame_height / 2 - y_center) ** 2)
    diagonal_pixels = math.sqrt(frame_width ** 2 + frame_height ** 2)
    
    percent_diagonal = distance_pixels / (diagonal_pixels if diagonal_pixels != 0 else 1.0)
    target_distance_meters = percent_diagonal * diagonal_distance
    
    # 5. Angle in frame coordinates (faithful to Roboflow JS formula)
    # Math.atan(norm_y / norm_x) * 180 / pi. If norm_x >= 0, add 180 degrees.
    angle = math.degrees(math.atan2(norm_y, norm_x if norm_x != 0 else 0.000001))
    
    # Let's map exactly Roboflow's custom quadrant adjustment:
    # var angle = Math.atan(normalized[0]/(normalized[1]||0.000001)) * 180 / Math.PI;
    # if(normalized[1] >= 0) angle += 180;
    raw_angle = math.degrees(math.atan(norm_y / (norm_x if norm_x != 0 else 0.000001)))
    if norm_x >= 0:
        raw_angle += 180.0
        
    # 6. Apply heading offsets
    # var bearing = (compass_heading - 90) % 360;
    # target_bearing = (bearing + angle) % 360
    base_bearing = (drone_heading - 90) % 360
    target_bearing = (base_bearing + raw_angle) % 360
    
    # 7. Project GPS coordinates
    target_lat, target_lon = geodesic_destination(drone_lat, drone_lon, target_distance_meters, target_bearing)
    
    return target_lat, target_lon
