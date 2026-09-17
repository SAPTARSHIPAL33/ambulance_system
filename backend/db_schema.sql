-- Emergency Hospital Routing System - Database Schema
-- Updated with realistic bed availability handling
-- Supports: range-based input, safety buffers, timestamp freshness

-- =============================================
-- 1. Hospitals Table (core hospital identity)
-- =============================================
CREATE TABLE hospitals (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    tier_level VARCHAR(50)
);

-- =============================================
-- 2. Hospital Resources Table (bed availability)
-- Includes last_updated for freshness tracking
-- =============================================
CREATE TABLE hospital_resources (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    icu_available INTEGER DEFAULT 0,        -- Conservative minimum (parsed from range input)
    emergency_beds INTEGER DEFAULT 0,       -- Conservative minimum (parsed from range input)
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(hospital_id)
);

-- Index for fast lookups during ranking
CREATE INDEX idx_hospital_resources_hospital_id ON hospital_resources(hospital_id);
CREATE INDEX idx_hospital_resources_last_updated ON hospital_resources(last_updated);

-- =============================================
-- 3. Doctor Availabilities Table
-- =============================================
CREATE TABLE doctor_availabilities (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    specialization VARCHAR(255),
    is_available BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_doctor_availabilities_hospital_id ON doctor_availabilities(hospital_id);

-- =============================================
-- 4. Emergency Cases Table
-- =============================================
CREATE TABLE emergency_cases (
    id SERIAL PRIMARY KEY,
    patient_condition TEXT NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    status VARCHAR(50) DEFAULT 'Pending',
    assigned_hospital_id INTEGER REFERENCES hospitals(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- MOCK DATA INSERTION (Bangalore hospitals)
-- =============================================

INSERT INTO hospitals (name, latitude, longitude, tier_level) VALUES
('Apollo Hospital Bannerghatta', 12.8958, 77.5986, 'Tier 1'),
('Fortis Hospital Cunningham Road', 12.9915, 77.5968, 'Tier 1'),
('Manipal Hospital Old Airport Road', 12.9592, 77.6479, 'Tier 1'),
('St. John''s Medical College Hospital', 12.9304, 77.6202, 'Tier 1'),
('Narayana Health City', 12.8078, 77.7022, 'Tier 1');

INSERT INTO hospital_resources (hospital_id, icu_available, emergency_beds, last_updated) VALUES
(1, 12, 25, CURRENT_TIMESTAMP),
(2, 8, 15, CURRENT_TIMESTAMP),
(3, 20, 40, CURRENT_TIMESTAMP),
(4, 15, 30, CURRENT_TIMESTAMP),
(5, 25, 50, CURRENT_TIMESTAMP);

INSERT INTO doctor_availabilities (hospital_id, specialization, is_available) VALUES
(1, 'Cardiology', TRUE),
(1, 'Neurology', TRUE),
(1, 'Oncology', TRUE),
(1, 'Trauma', TRUE),
(2, 'Cardiology', TRUE),
(2, 'Orthopedics', TRUE),
(2, 'General Surgery', TRUE),
(3, 'Multi-specialty', TRUE),
(3, 'Trauma', TRUE),
(3, 'Pediatrics', TRUE),
(3, 'Cardiology', TRUE),
(4, 'General Medicine', TRUE),
(4, 'Trauma', TRUE),
(4, 'Pediatrics', TRUE),
(4, 'Nephrology', TRUE),
(5, 'Cardiology', TRUE),
(5, 'Cardiac Surgery', TRUE),
(5, 'Organ Transplant', TRUE);

INSERT INTO emergency_cases (patient_condition, latitude, longitude, status) VALUES
('Severe Chest Pain, Suspected Cardiac Arrest', 12.9500, 77.6000, 'Pending');
