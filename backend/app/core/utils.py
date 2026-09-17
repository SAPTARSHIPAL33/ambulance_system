import math
import re
from datetime import datetime, timezone
from typing import Optional


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # Convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # Haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 6371  # Radius of earth in kilometers. Use 3956 for miles
    return c * r


# =============================================
# SAFETY BUFFER CONSTANTS
# These buffers simulate real-world uncertainty:
# walk-in patients, data lag, miscounted beds, etc.
# =============================================
ICU_SAFETY_BUFFER = 1       # Reserve 1 ICU bed as safety margin
BEDS_SAFETY_BUFFER = 2      # Reserve 2 emergency beds as safety margin

# =============================================
# FRESHNESS THRESHOLDS (in seconds)
# =============================================
FRESH_THRESHOLD_SECONDS = 120       # < 2 minutes  → data is fresh, no penalty
STALE_THRESHOLD_SECONDS = 600       # 2–10 minutes → slightly stale, small penalty
                                    # > 10 minutes → heavily stale, large penalty


def parse_range_to_minimum(range_str: str) -> int:
    """
    Parse a range string from the UI into the CONSERVATIVE MINIMUM value.
    
    This is the core of the realistic bed availability system.
    Hospitals report ranges because exact counts are unreliable in real-time.
    We always use the MINIMUM to avoid routing patients to full hospitals.
    
    Supported formats:
        "0-2"   → 0   (worst case: could be zero)
        "3-5"   → 3   (at least 3 available)
        "6-10"  → 6   (at least 6 available)
        "10+"   → 10  (at least 10, but could be more)
        "15"    → 15  (exact value, backward compatible)
    
    Args:
        range_str: A string like "3-5", "10+", or "15"
        
    Returns:
        The conservative minimum integer value
        
    Raises:
        ValueError: If the range string cannot be parsed
    """
    range_str = range_str.strip()
    
    # Case 1: "N+" format (e.g., "10+" means 10 or more)
    if range_str.endswith("+"):
        try:
            return int(range_str[:-1])
        except ValueError:
            raise ValueError(f"Invalid range format: '{range_str}'. Expected format like '10+'")
    
    # Case 2: "N-M" format (e.g., "3-5" means between 3 and 5)
    if "-" in range_str:
        parts = range_str.split("-")
        if len(parts) != 2:
            raise ValueError(f"Invalid range format: '{range_str}'. Expected format like '3-5'")
        try:
            low = int(parts[0])
            high = int(parts[1])
            if low > high:
                raise ValueError(f"Invalid range: minimum ({low}) > maximum ({high})")
            # Always return the conservative MINIMUM
            return low
        except ValueError as e:
            if "Invalid range" in str(e):
                raise
            raise ValueError(f"Invalid range format: '{range_str}'. Expected numeric values like '3-5'")
    
    # Case 3: Exact number (e.g., "15") — backward compatible
    try:
        return int(range_str)
    except ValueError:
        raise ValueError(f"Invalid range format: '{range_str}'. Expected a number, range (e.g., '3-5'), or open range (e.g., '10+')")


def apply_safety_buffer(stored_value: int, buffer: int) -> int:
    """
    Apply safety buffer to a stored bed count before using it in ranking.
    
    The buffer accounts for:
    - Walk-in patients who arrived after the last update
    - Data propagation delays
    - Beds temporarily unavailable for cleaning/maintenance
    
    Args:
        stored_value: The conservative minimum already stored in DB
        buffer: Number of beds to subtract as safety margin
        
    Returns:
        Usable bed count, never below 0
    """
    return max(0, stored_value - buffer)


def calculate_freshness_score(last_updated: Optional[datetime]) -> float:
    """
    Calculate a freshness multiplier based on how recently hospital
    resource data was updated.
    
    Stale data is unreliable — a hospital that reported 5 ICU beds 
    30 minutes ago may have 0 now. We penalize the ranking score
    for hospitals with outdated data.
    
    Freshness scoring:
        < 2 minutes old  → 1.0 (fully trusted, no penalty)
        2–10 minutes old → 0.7 (slightly stale, 30% penalty)
        > 10 minutes old → 0.3 (heavily stale, 70% penalty)
    
    Args:
        last_updated: Timestamp of last resource update (timezone-aware)
        
    Returns:
        A float between 0.0 and 1.0 representing data trustworthiness
    """
    if last_updated is None:
        # No timestamp means data was never explicitly updated → treat as very stale
        return 0.3
    
    # Ensure we compare timezone-aware datetimes
    now = datetime.now(timezone.utc)
    
    # Handle naive datetimes by assuming UTC
    if last_updated.tzinfo is None:
        last_updated = last_updated.replace(tzinfo=timezone.utc)
    
    age_seconds = (now - last_updated).total_seconds()
    
    if age_seconds < FRESH_THRESHOLD_SECONDS:
        # < 2 minutes: data is fresh, full trust
        return 1.0
    elif age_seconds < STALE_THRESHOLD_SECONDS:
        # 2–10 minutes: data is slightly stale
        # Linear interpolation from 1.0 to 0.7 across this window
        progress = (age_seconds - FRESH_THRESHOLD_SECONDS) / (STALE_THRESHOLD_SECONDS - FRESH_THRESHOLD_SECONDS)
        return 1.0 - (0.3 * progress)
    else:
        # > 10 minutes: data is heavily stale
        return 0.3


def get_confidence_level(last_updated: Optional[datetime]) -> str:
    """
    Return a human-readable confidence level based on data freshness.
    
    This is shown in the API response so dispatchers can make
    informed decisions about data reliability.
    
    Args:
        last_updated: Timestamp of last resource update
        
    Returns:
        "HIGH", "MEDIUM", or "LOW"
    """
    score = calculate_freshness_score(last_updated)
    
    if score >= 0.9:
        return "HIGH"
    elif score >= 0.5:
        return "MEDIUM"
    else:
        return "LOW"
