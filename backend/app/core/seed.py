import json
import os
import logging
from sqlalchemy.orm import Session
from app.models.hospital import Hospital, HospitalResource, DoctorAvailability
from app.core.database import engine, SessionLocal, Base

logger = logging.getLogger(__name__)

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "hospitals.json")

def load_hospitals_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def seed_database():
    db: Session = SessionLocal()
    try:
        # Check if we already have data
        existing_count = db.query(Hospital).count()
        if existing_count > 0:
            logger.info("Database already seeded with hospitals. Skipping seed.")
            return

        data = load_hospitals_data()
        if not data:
            logger.warning("No data found in hospitals.json to seed.")
            return

        for item in data:
            # 1. Create Hospital
            hospital = Hospital(
                name=item["name"],
                latitude=item["latitude"],
                longitude=item["longitude"],
                tier_level=item["tier_level"]
            )
            db.add(hospital)
            db.flush() # To get hospital.id

            # 2. Create HospitalResource
            resource = HospitalResource(
                hospital_id=hospital.id,
                icu_available=item.get("icu_available", 0),
                emergency_beds=item.get("emergency_beds", 0)
            )
            db.add(resource)

            # 3. Create DoctorAvailability records
            specs = item.get("specialization", "")
            if specs:
                # Split by comma and strip whitespace
                spec_list = [s.strip() for s in specs.split(",") if s.strip()]
                for spec in spec_list:
                    doc_avail = DoctorAvailability(
                        hospital_id=hospital.id,
                        specialization=spec,
                        is_available=True
                    )
                    db.add(doc_avail)

        db.commit()
        logger.info(f"Successfully seeded {len(data)} hospitals into the database.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
    finally:
        db.close()
