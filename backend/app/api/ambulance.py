"""
==============================================
AMBULANCE PORTAL — /api/ambulance
==============================================

Endpoints used by ambulance dispatch systems:
  - GET  /eligible-hospitals  → Find top 3 hospitals (ranked by proximity + freshness)
  - GET  /offline-region      → Bounding box for offline map caching
  - POST /send-alert          → Broadcast alert to hospitals
  - POST /process-case        → AI-powered case triage (NLP rule engine)

Access: Requires X-Role: ambulance (or admin)
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.ranking import find_best_hospitals
from app.core.mock_data import MOCK_HOSPITALS
from app.schemas.hospital import HospitalResponse, OfflineRegionResponse
from app.schemas.alert import AlertRequest, AlertResponse
from app.api.dependencies import require_ambulance_role

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================
# GET /eligible-hospitals
# =============================================

@router.get("/eligible-hospitals", response_model=List[HospitalResponse])
def get_eligible_hospitals(
    victim_lat: float = Query(..., description="Latitude of the victim", ge=-90, le=90),
    victim_lon: float = Query(..., description="Longitude of the victim", ge=-180, le=180),
    specialization: Optional[str] = Query(None, description="Required doctor specialization"),
    severity: str = Query("Medium", description="Severity of the case (Low, Medium, High, Critical)"),
    db: Session = Depends(get_db),
    role: str = Depends(require_ambulance_role),
):
    """
    Retrieves top 3 eligible hospitals ranked by proximity and data freshness.

    Includes:
    - Safety-buffered bed counts (usable after uncertainty margin)
    - Freshness score (how recent the resource data is)
    - Confidence level (HIGH/MEDIUM/LOW for dispatcher awareness)

    Response format is backward compatible — new fields are optional.
    """
    logger.info(f"[Ambulance] Filtering hospitals for ({victim_lat}, {victim_lon}), spec: {specialization}, role: {role}")

    try:
        top_3 = find_best_hospitals(db, victim_lat, victim_lon, specialization)

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
# GET /offline-region
# =============================================

@router.get("/offline-region", response_model=OfflineRegionResponse)
def get_offline_region(
    ambulance_lat: float = Query(..., ge=-90, le=90),
    ambulance_lon: float = Query(..., ge=-180, le=180),
    victim_lat: float = Query(..., ge=-90, le=90),
    victim_lon: float = Query(..., ge=-180, le=180),
    specialization: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    role: str = Depends(require_ambulance_role),
):
    """
    Calculate deterministic offline region bounding box.
    Includes: Ambulance, Victim, and Top 3 Eligible Hospitals.
    """
    try:
        # 1. Get Top 3 Hospitals
        best_hospitals = find_best_hospitals(db, victim_lat, victim_lon, specialization)

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
            max_lon=max_lon + margin,
        )

    except Exception as e:
        logger.error(f"Error calculating offline region: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


# =============================================
# POST /send-alert
# =============================================

@router.post("/send-alert", response_model=AlertResponse, status_code=status.HTTP_200_OK)
def send_alert(
    alert: AlertRequest,
    role: str = Depends(require_ambulance_role),
):
    """
    Simulate sending alerts to multiple hospitals.
    Logic:
    - Iterate hospital_ids.
    - Log "Alert sent to Hospital X".
    - Pick first one as "Confirmed".
    - Log "Hospital X confirmed".
    - Log "Hospital Y released" for others.
    """
    logger.info(f"[Ambulance] Broadcasting alert for Case {alert.case_id} to hospitals: {alert.hospital_ids}")

    confirmed_hospital = None

    for i, h_id in enumerate(alert.hospital_ids):
        # Validate hospital exists (Mock)
        hospital = next((h for h in MOCK_HOSPITALS if h["id"] == h_id), None)
        hospital_name = hospital["name"] if hospital else f"ID {h_id}"

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
        message=f"Alert confirmed by {confirmed_hospital['name']}",
        status="confirmed",
        confirmed_hospital_id=confirmed_hospital["id"],
        case_id=alert.case_id,
    )


# =============================================
# POST /process-case (AI Triage — moved from ai.py)
# =============================================

class CaseInput(BaseModel):
    description: str


class CaseAnalysis(BaseModel):
    specialization: str
    severity: str


@router.post("/process-case", response_model=CaseAnalysis)
def process_case(
    case: CaseInput,
    role: str = Depends(require_ambulance_role),
):
    """
    Analyze case description to determine required specialization and severity.
    Rule-based NLP for hackathon demo.
    """
    desc = case.description.lower()

    spec = "General"
    severity = "Low"

    # Rule-Based Logic
    if any(k in desc for k in ["cardiac", "heart", "chest pain", "attack"]):
        spec = "Cardiology"
        severity = "High"
    elif any(k in desc for k in ["stroke", "brain", "head", "seizure", "unconscious"]):
        spec = "Neurology"
        severity = "High"
    elif any(k in desc for k in ["bleeding", "fracture", "accident", "trauma", "crash", "burn"]):
        spec = "Trauma"
        severity = "Medium"
    elif any(k in desc for k in ["child", "baby", "pediatric"]):
        spec = "Pediatrics"
        severity = "Medium"
    elif any(k in desc for k in ["breath", "lung", "asthma"]):
        spec = "Pulmonology"
        severity = "Medium"

    # Keyword override for critical severity
    if any(k in desc for k in ["severe", "critical", "dying", "unresponsive", "massive"]):
        severity = "Critical"

    return CaseAnalysis(specialization=spec, severity=severity)
