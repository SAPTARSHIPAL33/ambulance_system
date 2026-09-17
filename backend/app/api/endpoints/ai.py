from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class CaseInput(BaseModel):
    description: str

class CaseAnalysis(BaseModel):
    specialization: str
    severity: str

@router.post("/process-case", response_model=CaseAnalysis)
def process_case(case: CaseInput):
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
