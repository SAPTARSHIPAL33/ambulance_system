from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class EmergencyCaseCreate(BaseModel):
    patient_condition: str
    latitude: float
    longitude: float

class EmergencyCaseResponse(BaseModel):
    id: int
    patient_condition: str
    latitude: float
    longitude: float
    status: str
    assigned_hospital_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True
