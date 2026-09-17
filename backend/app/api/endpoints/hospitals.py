import logging
import math
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.core.utils import (
    calculate_distance,
    parse_range_to_minimum,
    apply_safety_buffer,
    calculate_freshness_score,
    get_confidence_level,
    ICU_SAFETY_BUFFER,
    BEDS_SAFETY_BUFFER,
)
from app.core.database import get_db
from app.models.hospital import Hospital, HospitalResource, DoctorAvailability
from app.schemas.hospital import (
    HospitalResponse,
    HospitalCreate,
    OfflineRegionResponse,
    ResourceRangeUpdateRequest,
    ResourceRangeUpdateResponse,
)

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================
# EXISTING: Create Hospital (unchanged for backward compat)
# =============================================

@router.post("/", response_model=HospitalResponse)
def create_hospital(hospital: HospitalCreate, db: Session = Depends(get_db)):
    """
    Create a new hospital in the database.
    Backward compatible — accepts exact integer values.
    """
    try:
        new_hospital = Hospital(
            name=hospital.name,
            latitude=hospital.latitude,
            longitude=hospital.longitude,
            tier_level=hospital.tier_level
        )
        db.add(new_hospital)
        db.flush()

        resource = HospitalResource(
            hospital_id=new_hospital.id,
            icu_available=hospital.icu_available,
            emergency_beds=hospital.emergency_beds
        )
        db.add(resource)

        if hospital.specialization:
            specs = [s.strip() for s in hospital.specialization.split(",") if s.strip()]
            for spec in specs:
                doc_avail = DoctorAvailability(
                    hospital_id=new_hospital.id,
                    specialization=spec,
                    is_available=True
                )
                db.add(doc_avail)

        db.commit()

        return {
            "id": new_hospital.id,
            "name": new_hospital.name,
            "latitude": new_hospital.latitude,
            "longitude": new_hospital.longitude,
            "tier_level": new_hospital.tier_level,
            "icu_available": hospital.icu_available,
            "emergency_beds": hospital.emergency_beds,
            "specialization": hospital.specialization,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating hospital: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


# =============================================
# NEW: Range-Based Resource Update Endpoint
# =============================================

@router.post("/update-resources-range", response_model=ResourceRangeUpdateResponse)
def update_resources_range(
    request: ResourceRangeUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Update hospital resource availability using RANGE-BASED input.
    
    This endpoint is designed for real-world uncertainty. Instead of
    requiring exact bed counts (which are unreliable in busy ERs),
    hospitals report ranges like "6-10" or "10+".
    
    The system converts these to CONSERVATIVE MINIMUMS:
        "0-2"   → stores 0
        "3-5"   → stores 3
        "6-10"  → stores 6
        "10+"   → stores 10
    
    This ensures we NEVER route a patient to a hospital that might
    actually be full — we always use the worst-case estimate.
    
    The last_updated timestamp is automatically set to NOW.
    """
    # 1. Validate hospital exists
    hospital = db.query(Hospital).filter(Hospital.id == request.hospital_id).first()
    if not hospital:
        raise HTTPException(
            status_code=404,
            detail=f"Hospital with ID {request.hospital_id} not found"
        )

    # 2. Parse ranges into conservative minimums
    try:
        icu_minimum = parse_range_to_minimum(request.icu_range)
        beds_minimum = parse_range_to_minimum(request.beds_range)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(
        f"Range update for Hospital {request.hospital_id}: "
        f"ICU '{request.icu_range}' → {icu_minimum}, "
        f"Beds '{request.beds_range}' → {beds_minimum}"
    )

    # 3. Update or create hospital resource record
    resource = db.query(HospitalResource).filter(
        HospitalResource.hospital_id == request.hospital_id
    ).first()

    now_utc = datetime.now(timezone.utc)

    if resource:
        # Update existing record
        resource.icu_available = icu_minimum
        resource.emergency_beds = beds_minimum
        resource.last_updated = now_utc
    else:
        # Create new resource record (edge case: hospital exists but no resource row)
        resource = HospitalResource(
            hospital_id=request.hospital_id,
            icu_available=icu_minimum,
            emergency_beds=beds_minimum,
            last_updated=now_utc
        )
        db.add(resource)

    db.commit()
    db.refresh(resource)

    logger.info(
        f"Resource updated for Hospital {request.hospital_id} "
        f"('{hospital.name}'): ICU={icu_minimum}, Beds={beds_minimum}"
    )

    return ResourceRangeUpdateResponse(
        hospital_id=hospital.id,
        hospital_name=hospital.name,
        icu_stored=icu_minimum,
        beds_stored=beds_minimum,
        icu_range_received=request.icu_range,
        beds_range_received=request.beds_range,
        last_updated=resource.last_updated,
        message=(
            f"Resources updated successfully. "
            f"ICU: '{request.icu_range}' → {icu_minimum} (conservative min), "
            f"Beds: '{request.beds_range}' → {beds_minimum} (conservative min). "
            f"Safety buffers (ICU: -{ICU_SAFETY_BUFFER}, Beds: -{BEDS_SAFETY_BUFFER}) "
            f"will be applied during ranking."
        )
    )


# =============================================
# UPDATED: Hospital Ranking with Buffer + Freshness
# =============================================

def _find_best_hospitals(
    db: Session,
    lat: float,
    lon: float,
    specialization: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Internal helper to find top 3 hospitals ranked by a composite score.
    
    RANKING ALGORITHM (updated with realistic uncertainty handling):
    
    1. SAFETY BUFFER: Before evaluating, subtract buffers from stored values:
       - usable_icu  = max(0, icu_available  - ICU_SAFETY_BUFFER)
       - usable_beds = max(0, emergency_beds - BEDS_SAFETY_BUFFER)
       
       This accounts for walk-in patients and data lag.
    
    2. FRESHNESS PENALTY: Hospitals with stale data get penalized:
       - < 2 min old  → freshness_score = 1.0 (no penalty)
       - 2–10 min old → freshness_score = 0.7–1.0 (slight penalty)
       - > 10 min old → freshness_score = 0.3 (heavy penalty)
    
    3. COMPOSITE SCORE = (1 / distance) * freshness_score
       Lower distance = higher score, stale data = lower score.
       
    4. Only hospitals with usable_icu > 0 (after buffer) are eligible.
    
    Returns list of dicts sorted by composite score (best first).
    """
    query = db.query(Hospital).join(HospitalResource)

    if specialization:
        query = query.join(DoctorAvailability).filter(
            DoctorAvailability.specialization.ilike(f"%{specialization}%"),
            DoctorAvailability.is_available == True
        )

    # Fetch all hospitals that have resources (we'll filter by buffer below)
    db_hospitals = query.all()

    candidates = []
    for h in db_hospitals:
        if not h.resource:
            continue

        # --- SAFETY BUFFER APPLICATION ---
        # Subtract buffers BEFORE eligibility check and ranking.
        # This is the conservative estimate of ACTUALLY USABLE beds.
        raw_icu = h.resource.icu_available
        raw_beds = h.resource.emergency_beds
        
        usable_icu = apply_safety_buffer(raw_icu, ICU_SAFETY_BUFFER)
        usable_beds = apply_safety_buffer(raw_beds, BEDS_SAFETY_BUFFER)

        # Filter: hospital must have at least 1 usable ICU bed AFTER buffer
        if usable_icu <= 0:
            logger.debug(
                f"Skipping '{h.name}': raw ICU={raw_icu}, "
                f"after buffer ({ICU_SAFETY_BUFFER})={usable_icu} — not enough"
            )
            continue

        # --- FRESHNESS SCORING ---
        last_updated = h.resource.last_updated
        freshness = calculate_freshness_score(last_updated)
        confidence = get_confidence_level(last_updated)

        specs = [d.specialization for d in h.doctor_availabilities if d.is_available]

        candidate = {
            "id": h.id,
            "name": h.name,
            "latitude": h.latitude,
            "longitude": h.longitude,
            "tier_level": h.tier_level,
            # Report the USABLE values (after buffer), not raw values
            "icu_available": usable_icu,
            "emergency_beds": usable_beds,
            "specialization": ", ".join(specs),
            # New freshness/confidence fields
            "last_updated": last_updated.isoformat() if last_updated else None,
            "freshness_score": round(freshness, 2),
            "confidence_level": confidence,
        }
        candidates.append((candidate, freshness))

    # --- COMPOSITE SCORING ---
    scored_hospitals = []
    for candidate, freshness in candidates:
        dist = calculate_distance(lat, lon, candidate["latitude"], candidate["longitude"])

        # Composite score: proximity × data freshness
        # Higher is better. We avoid division by zero with a small epsilon.
        proximity_score = 1.0 / max(dist, 0.01)
        composite_score = proximity_score * freshness

        scored_hospitals.append({
            "hospital": candidate,
            "distance": dist,
            "composite_score": composite_score,
        })

    # Sort by composite score (highest first = closest + freshest)
    scored_hospitals.sort(key=lambda x: x["composite_score"], reverse=True)
    return scored_hospitals[:3]


# =============================================
# EXISTING: Get Eligible Hospitals (response format preserved)
# =============================================

@router.get("/eligible-hospitals", response_model=List[HospitalResponse])
def get_eligible_hospitals(
    victim_lat: float = Query(..., description="Latitude of the victim", ge=-90, le=90),
    victim_lon: float = Query(..., description="Longitude of the victim", ge=-180, le=180),
    specialization: Optional[str] = Query(None, description="Required doctor specialization"),
    severity: str = Query("Medium", description="Severity of the case (Low, Medium, High, Critical)"),
    db: Session = Depends(get_db)
):
    """
    Retrieves top 3 eligible hospitals ranked by proximity and data freshness.
    
    Now includes:
    - Safety-buffered bed counts (usable after uncertainty margin)
    - Freshness score (how recent the resource data is)
    - Confidence level (HIGH/MEDIUM/LOW for dispatcher awareness)
    
    Response format is backward compatible — new fields are optional.
    """
    logger.info(f"Filtering hospitals for location: ({victim_lat}, {victim_lon}), spec: {specialization}")

    try:
        top_3 = _find_best_hospitals(db, victim_lat, victim_lon, specialization)

        result = []
        for item in top_3:
            h = item["hospital"].copy()
            h["distance_km"] = round(item["distance"], 2)
            result.append(h)

        return result

    except Exception as e:
        logger.error(f"Error retrieving hospitals: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


# =============================================
# EXISTING: Offline Region (unchanged)
# =============================================

@router.get("/offline-region", response_model=OfflineRegionResponse)
def get_offline_region(
    ambulance_lat: float = Query(..., ge=-90, le=90),
    ambulance_lon: float = Query(..., ge=-180, le=180),
    victim_lat: float = Query(..., ge=-90, le=90),
    victim_lon: float = Query(..., ge=-180, le=180),
    specialization: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Calculate deterministic offline region bounding box.
    Includes: Ambulance, Victim, and Top 3 Eligible Hospitals.
    """
    try:
        # 1. Get Top 3 Hospitals
        best_hospitals = _find_best_hospitals(db, victim_lat, victim_lon, specialization)

        # 2. Collect all points
        lats = [ambulance_lat, victim_lat]
        lons = [ambulance_lon, victim_lon]

        for item in best_hospitals:
            h = item["hospital"]
            lats.append(h["latitude"])
            lons.append(h["longitude"])

        # 3. Compute Min/Max
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

        # 4. Add margin (0.01 degrees ~= 1.1km)
        margin = 0.01

        return OfflineRegionResponse(
            min_lat=min_lat - margin,
            max_lat=max_lat + margin,
            min_lon=min_lon - margin,
            max_lon=max_lon + margin
        )

    except Exception as e:
        logger.error(f"Error calculating offline region: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
