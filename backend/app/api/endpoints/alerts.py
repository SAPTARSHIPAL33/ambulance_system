import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.hospital import Hospital
from app.schemas.alert import AlertRequest, AlertResponse

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/send-alert", response_model=AlertResponse, status_code=status.HTTP_200_OK)
def send_alert(
    alert: AlertRequest,
    db: Session = Depends(get_db),
):
    """
    Send alerts to multiple hospitals.
    Logic:
    - Iterate hospital_ids, querying each from the database.
    - Log "Alert sent to Hospital X".
    - Pick first one as "Confirmed".
    - Log "Hospital X confirmed".
    - Log "Hospital Y released" for others.
    """
    logger.info(f"Broadcasting alert for Case {alert.case_id} to hospitals: {alert.hospital_ids}")
    
    confirmed_hospital = None
    
    for i, h_id in enumerate(alert.hospital_ids):
        # Query hospital from the database
        hospital = db.query(Hospital).filter(Hospital.id == h_id).first()
        hospital_name = hospital.name if hospital else f"ID {h_id}"
        
        print(f"Alert sent to {hospital_name}")
        logger.info(f"Alert sent to {hospital_name}")
        
        if i == 0:
            # First one confirms
            confirmed_hospital = hospital
            print(f"{hospital_name} confirmed")
            logger.info(f"{hospital_name} confirmed assignment for Case {alert.case_id}")
        else:
            # Others are released
            print(f"{hospital_name} released")
            logger.info(f"{hospital_name} released for Case {alert.case_id}")

    if not confirmed_hospital:
        raise HTTPException(status_code=404, detail="No valid hospitals found to assign")

    return AlertResponse(
        message=f"Alert confirmed by {confirmed_hospital.name}",
        status="confirmed",
        confirmed_hospital_id=confirmed_hospital.id,
        case_id=alert.case_id
    )

