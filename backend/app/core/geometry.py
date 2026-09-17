from typing import List, Tuple, Dict

def calculate_bounding_box(
    ambulance_loc: Tuple[float, float],
    victim_loc: Tuple[float, float],
    hospitals: List[Tuple[float, float]],
    route_polyline: List[Tuple[float, float]],
    buffer_ratio: float = 0.1
) -> Dict[str, float]:
    """
    Calculates the minimum bounding box covering all critical entities with a continuity buffer.
    
    Args:
        ambulance_loc: (lat, lon) of ambulance
        victim_loc: (lat, lon) of victim
        hospitals: List of (lat, lon) for top eligible hospitals
        route_polyline: List of (lat, lon) points defining the route
        buffer_ratio: Percentage of valid width/height to add as padding (default 10%)
        
    Returns:
        Dict with min_lat, max_lat, min_lon, max_lon
    """
    # 1. Consolidate all points (lat, lon)
    points = [ambulance_loc, victim_loc] + hospitals + route_polyline
    
    if not points:
        # Fallback for empty data (should not happen in valid flow)
        return {"min_lat": 0, "max_lat": 0, "min_lon": 0, "max_lon": 0}

    # 2. Extract Latitudes and Longitudes
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    
    # 3. Determine Extent
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    
    # 4. Calculate Dimensions & Buffer
    lat_diff = max_lat - min_lat
    lon_diff = max_lon - min_lon
    
    # Handle single point or collinear cases by ensuring minimal buffer
    MIN_BUFFER_DEG = 0.005  # Approx 500m
    
    lat_buffer = max(lat_diff * buffer_ratio, MIN_BUFFER_DEG)
    lon_buffer = max(lon_diff * buffer_ratio, MIN_BUFFER_DEG)
    
    # 5. Apply Buffer
    return {
        "min_lat": float(min_lat - lat_buffer),
        "max_lat": float(max_lat + lat_buffer),
        "min_lon": float(min_lon - lon_buffer),
        "max_lon": float(max_lon + lon_buffer)
    }
