"""
Hospital ranking service — shared business logic.

This module contains the core ranking algorithm used by the ambulance
portal to find the best hospitals. It is extracted here so multiple
routers can import it without circular dependencies.
"""

import logging
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from app.core.utils import (
    calculate_distance,
    apply_safety_buffer,
    calculate_freshness_score,
    get_confidence_level,
    ICU_SAFETY_BUFFER,
    BEDS_SAFETY_BUFFER,
)
from app.models.hospital import Hospital, HospitalResource, DoctorAvailability

logger = logging.getLogger(__name__)


def get_resource_score(val) -> float:
    """
    Convert ICU and bed values (strings or ints) into numeric scores.
    "0-2" -> 1
    "3-5" -> 2
    "6-10" -> 3
    "10+" -> 4
    """
    if isinstance(val, str):
        if val == "0-2": return 1.0
        elif val == "3-5": return 2.0
        elif val == "6-10": return 3.0
        elif val == "10+": return 4.0
        return 1.0
    
    # Handle raw integers that are converted in database
    if val < 3: return 1.0
    elif val < 6: return 2.0
    elif val < 10: return 3.0
    return 4.0

def find_best_hospitals(
    db: Session,
    lat: float,
    lon: float,
    specialization: Optional[str] = None
) -> List[Dict[str, Any]]:
    # ... docstrings truncated for length if preferred ...
    query = db.query(Hospital).join(HospitalResource)

    if specialization:
        query = query.join(DoctorAvailability).filter(
            DoctorAvailability.specialization.ilike(f"%{specialization}%"),
            DoctorAvailability.is_available == True
        )

    db_hospitals = query.all()

    candidates = []
    for h in db_hospitals:
        if not h.resource:
            continue

        raw_icu = h.resource.icu_available
        raw_beds = h.resource.emergency_beds

        usable_icu = apply_safety_buffer(raw_icu, ICU_SAFETY_BUFFER)
        usable_beds = apply_safety_buffer(raw_beds, BEDS_SAFETY_BUFFER)

        if usable_icu <= 0:
            logger.debug(
                f"Skipping '{h.name}': raw ICU={raw_icu}, "
                f"after buffer ({ICU_SAFETY_BUFFER})={usable_icu} — not enough"
            )
            continue

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
            "icu_available": usable_icu,
            "emergency_beds": usable_beds,
            "specialization": ", ".join(specs),
            "last_updated": last_updated.isoformat() if last_updated else None,
            "freshness_score": round(freshness, 2),
            "confidence_level": confidence,
            "raw_icu": raw_icu,
            "raw_beds": raw_beds,
        }
        candidates.append((candidate, freshness))

    scored_hospitals = []
    for candidate, freshness in candidates:
        dist = calculate_distance(lat, lon, candidate["latitude"], candidate["longitude"])
        
        # 1. Convert resource values to numeric scores
        # We use raw_icu/raw_beds because they represent the original bucket from the UI
        icu_score = get_resource_score(candidate["raw_icu"])
        beds_score = get_resource_score(candidate["raw_beds"])

        # 1.5 Strict capability threshold filtering
        if icu_score < 2.0 or beds_score < 2.0:
            logger.debug(f"Filtering out {candidate['name']} due to low resources: icu_score={icu_score}, beds_score={beds_score}")
            continue
        distance_km = float(dist)
        freshness_score = float(candidate["freshness_score"])

        # 2. Correct Scoring Formula
        composite_score = (
            (icu_score * 0.4) + 
            (beds_score * 0.3) + 
            (freshness_score * 0.2) - 
            (distance_km * 0.1)
        )

        # 3. Debug Output (TEMPORARY)
        print(f"Hospital: {candidate['name']} | ICU Score: {icu_score} | Beds Score: {beds_score} | Distance: {distance_km:.2f}km | Final Score: {composite_score:.2f}")

        scored_hospitals.append({
            "hospital": candidate,
            "distance": dist,
            "composite_score": composite_score,
        })

    # Sort descending
    scored_hospitals.sort(key=lambda x: x["composite_score"], reverse=True)
    return scored_hospitals[:3]
