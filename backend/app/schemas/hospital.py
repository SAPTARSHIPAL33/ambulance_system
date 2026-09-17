from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class HospitalCreate(BaseModel):
    """Schema for creating a new hospital (backward compatible)."""
    name: str
    latitude: float
    longitude: float
    tier_level: str
    icu_available: int
    emergency_beds: int
    specialization: str


class HospitalResponse(BaseModel):
    """
    Standard hospital response — backward compatible with existing clients.
    New fields (confidence_level, last_updated, freshness_score) are optional
    so old consumers are unaffected.
    """
    id: int
    name: str
    latitude: float
    longitude: float

    tier_level: str
    icu_available: int
    emergency_beds: int
    specialization: str

    # Distance is computed at runtime
    distance_km: Optional[float] = None

    # --- NEW: Freshness & Confidence Fields (optional for backward compat) ---
    last_updated: Optional[datetime] = None
    freshness_score: Optional[float] = None
    confidence_level: Optional[str] = None  # "HIGH" / "MEDIUM" / "LOW"

    class Config:
        from_attributes = True


class OfflineRegionResponse(BaseModel):
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float


# =============================================
# NEW: Range-Based Resource Update Schemas
# =============================================

class ResourceRangeUpdateRequest(BaseModel):
    """
    Request schema for range-based resource updates.
    
    Hospitals report availability as RANGES instead of exact numbers
    because in a busy ER, exact counts are unreliable.
    
    Example:
        {
            "hospital_id": 2,
            "icu_range": "6-10",
            "beds_range": "10+"
        }
    
    The backend will convert these to conservative minimums:
        "6-10" → 6  (at least 6 ICU beds)
        "10+"  → 10 (at least 10 emergency beds)
    """
    hospital_id: int
    icu_range: str       # e.g., "0-2", "3-5", "6-10", "10+"
    beds_range: str      # e.g., "0-2", "3-5", "6-10", "10+"

    @field_validator("icu_range", "beds_range")
    @classmethod
    def validate_range_format(cls, v: str) -> str:
        """Validate that the range string looks reasonable before processing."""
        v = v.strip()
        if not v:
            raise ValueError("Range cannot be empty")
        # Allow: digits, +, - (as separator)
        import re
        if not re.match(r"^\d+(\-\d+|\+)?$", v):
            raise ValueError(
                f"Invalid range format: '{v}'. "
                "Expected formats: '5' (exact), '3-5' (range), or '10+' (open-ended)"
            )
        return v


class ResourceRangeUpdateResponse(BaseModel):
    """
    Response after a range-based resource update.
    Shows what was parsed and stored so the caller can verify.
    """
    hospital_id: int
    hospital_name: str
    icu_stored: int           # The conservative minimum stored in DB
    beds_stored: int          # The conservative minimum stored in DB
    icu_range_received: str   # Echo back what was received
    beds_range_received: str  # Echo back what was received
    last_updated: datetime
    message: str
