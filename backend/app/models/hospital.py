from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    latitude = Column(Float, index=True)
    longitude = Column(Float, index=True)
    tier_level = Column(String)  # e.g., "Tier 1", "Tier 2"

    resource = relationship("HospitalResource", back_populates="hospital", uselist=False)
    doctor_availabilities = relationship("DoctorAvailability", back_populates="hospital")
    emergency_cases = relationship("EmergencyCase", back_populates="assigned_hospital")

class HospitalResource(Base):
    __tablename__ = "hospital_resources"

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), index=True)
    icu_available = Column(Integer, default=0)
    emergency_beds = Column(Integer, default=0)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    hospital = relationship("Hospital", back_populates="resource")

class DoctorAvailability(Base):
    __tablename__ = "doctor_availabilities"

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), index=True)
    specialization = Column(String)
    is_available = Column(Boolean, default=True)

    hospital = relationship("Hospital", back_populates="doctor_availabilities")

class EmergencyCase(Base):
    __tablename__ = "emergency_cases"

    id = Column(Integer, primary_key=True, index=True)
    patient_condition = Column(Text, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    status = Column(String, default='Pending')
    assigned_hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    assigned_hospital = relationship("Hospital", back_populates="emergency_cases")
