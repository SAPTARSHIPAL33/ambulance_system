"""
==============================================
ADMIN PORTAL — /api/admin
==============================================

Endpoints for system administrators:
  - POST /create-hospital  → Add a new hospital to the system

Access: Requires X-Role: admin
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hospital import Hospital, HospitalResource, DoctorAvailability
from app.schemas.hospital import HospitalResponse, HospitalCreate
from app.api.dependencies import require_admin_role

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================
# POST /create-hospital
# =============================================

@router.post("/create-hospital", response_model=HospitalResponse)
def create_hospital(
    hospital: HospitalCreate,
    db: Session = Depends(get_db),
    role: str = Depends(require_admin_role),
):
    """
    Create a new hospital in the database.
    Backward compatible — accepts exact integer values.
    Only accessible by admin role.
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

        logger.info(f"[Admin] Created hospital '{hospital.name}' (ID: {new_hospital.id}) by role: {role}")

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
