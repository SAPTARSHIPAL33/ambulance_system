"""
==============================================
HOSPITAL PORTAL — /api/hospital
==============================================

Endpoints used by hospital staff to update their own resource data:
  - POST /update-resources-range  → Report bed/ICU availability as ranges

Access: Requires X-Role: hospital (or admin)
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.utils import (
    parse_range_to_minimum,
    ICU_SAFETY_BUFFER,
    BEDS_SAFETY_BUFFER,
)
from app.models.hospital import Hospital, HospitalResource
from app.schemas.hospital import ResourceRangeUpdateRequest, ResourceRangeUpdateResponse
from app.api.dependencies import require_hospital_role

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================
# POST /update-resources-range
# =============================================

@router.post("/update-resources-range", response_model=ResourceRangeUpdateResponse)
def update_resources_range(
    request: ResourceRangeUpdateRequest,
    db: Session = Depends(get_db),
    role: str = Depends(require_hospital_role),
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
        f"[Hospital] Range update for Hospital {request.hospital_id}: "
        f"ICU '{request.icu_range}' → {icu_minimum}, "
        f"Beds '{request.beds_range}' → {beds_minimum} (role: {role})"
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
        f"[Hospital] Resource updated for Hospital {request.hospital_id} "
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
