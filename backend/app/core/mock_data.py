import json
import os
import logging

logger = logging.getLogger(__name__)

# Path to the JSON file
DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "hospitals.json")

def load_hospitals():
    """Load hospitals from JSON file."""
    try:
        if not os.path.exists(DATA_FILE):
            logger.warning(f"Hospital data file not found at {DATA_FILE}. Using empty list.")
            return []
        
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            logger.info(f"Loaded {len(data)} hospitals from {DATA_FILE}")
            return data
    except Exception as e:
        logger.error(f"Error loading hospital data: {e}")
        return []

# Load data at module level
MOCK_HOSPITALS = load_hospitals()

# Simple in-memory storage for cases
MOCK_CASES = []
