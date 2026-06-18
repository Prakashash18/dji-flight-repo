import unittest
import math
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from georeferencing import georeference_box, TelemetryInterpolator, geodesic_destination

class TestGeoreferencingMath(unittest.TestCase):
    
    def test_center_projection(self):
        """If the detection is exactly in the center, it should project to the drone's position."""
        drone_lat = 1.3521
        drone_lon = 103.8198
        drone_alt = 30.0 # meters
        drone_heading = 45.0 # degrees
        
        # Frame size 1920x1080
        # Detection center is (960, 540)
        target_lat, target_lon = georeference_box(
            x_center=960,
            y_center=540,
            frame_width=1920,
            frame_height=1080,
            drone_lat=drone_lat,
            drone_lon=drone_lon,
            drone_alt=drone_alt,
            drone_heading=drone_heading
        )
        
        # Due to float precision and default fov, it might have very tiny deviation from center
        self.assertAlmostEqual(target_lat, drone_lat, places=5)
        self.assertAlmostEqual(target_lon, drone_lon, places=5)
        
    def test_geodesic_destination(self):
        """Test geodesic destination calculations."""
        # Start at 0, 0 and move north by 111,195 meters (approx 1 degree lat)
        new_lat, new_lon = geodesic_destination(0.0, 0.0, 111195.0, 0.0)
        self.assertAlmostEqual(new_lat, 1.0, places=1)
        self.assertAlmostEqual(new_lon, 0.0, places=5)

    def test_telemetry_interpolation(self):
        """Test circular interpolation for heading."""
        # Create a mock telemetry csv content
        interpolator = TelemetryInterpolator()
        import pandas as pd
        df = pd.DataFrame({
            'timestamp_ms': [0, 1000],
            'latitude': [1.0, 1.0],
            'longitude': [100.0, 100.0],
            'altitude': [10.0, 20.0],
            'heading': [350.0, 10.0]  # wraps around 360
        })
        temp_csv = 'test_temp_telemetry.csv'
        df.to_csv(temp_csv, index=False)
        
        try:
            interpolator.load_from_csv(temp_csv)
            # Interpolate halfway (500ms)
            # 350 to 10 halfway wrapping around 360 is 0.0 degrees!
            state = interpolator.get_location(500)
            self.assertAlmostEqual(state['latitude'], 1.0)
            self.assertAlmostEqual(state['altitude'], 15.0)
            self.assertAlmostEqual(state['heading'] % 360, 0.0)
        finally:
            if os.path.exists(temp_csv):
                os.remove(temp_csv)

if __name__ == "__main__":
    unittest.main()
