from pydantic import BaseModel
from typing import List, Optional

class AlertRequest(BaseModel):
    hospital_ids: List[int]
    case_id: str

class AlertResponse(BaseModel):
    message: str
    status: str
    confirmed_hospital_id: Optional[int] = None
    case_id: str
