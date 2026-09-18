# 🚑 Emergency Hospital Routing System

> Real-time ambulance dispatch and hospital routing platform for Bangalore — built for emergency triage, intelligent hospital ranking, and coordinated alert management.

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%2019-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Vite](https://img.shields.io/badge/Bundler-Vite-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![Docker](https://img.shields.io/badge/Container-Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

---

## 📖 Overview

The **Emergency Hospital Routing System** is a full-stack application that optimizes ambulance dispatch by ranking nearby hospitals based on multiple real-time factors:

- **Proximity** — Haversine distance from the victim's location
- **Resource availability** — ICU beds and emergency beds with safety-buffered counts
- **Data freshness** — How recently the hospital updated its resource data
- **Specialization** — Whether the hospital has the required medical specialization available

The system serves three distinct user roles through separate portals:

| Portal | Role | Purpose |
|--------|------|---------|
| 🚑 **Ambulance Portal** | `ambulance` | Dispatch & routing — find eligible hospitals, triage cases, send alerts |
| 🏥 **Hospital Portal** | `hospital` | Resource management — report bed/ICU availability as ranges |
| 🔧 **Admin Portal** | `admin` | System administration — create hospitals, manage system-level data |

---

## 🏗️ Architecture

```
AmbulanceSystem/
├── backend/                    # FastAPI REST API
│   ├── app/
│   │   ├── api/                # Route handlers (role-based portals)
│   │   │   ├── ambulance.py    # Ambulance portal endpoints
│   │   │   ├── hospital.py     # Hospital portal endpoints
│   │   │   ├── admin.py        # Admin portal endpoints
│   │   │   ├── dependencies.py # RBAC middleware (X-Role header)
│   │   │   └── endpoints/      # Additional endpoint modules
│   │   ├── core/               # Business logic & utilities
│   │   │   ├── config.py       # Pydantic settings (env-based)
│   │   │   ├── database.py     # SQLAlchemy engine & session
│   │   │   ├── ranking.py      # Hospital ranking algorithm
│   │   │   ├── geometry.py     # Geospatial calculations
│   │   │   ├── utils.py        # Range parsing, safety buffers, freshness
│   │   │   └── seed.py         # Mock data seeder
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── data/               # Static data (hospitals.json)
│   │   └── main.py             # FastAPI app entrypoint
│   ├── db_schema.sql           # Database schema + mock data
│   ├── Dockerfile              # Backend container image
│   ├── requirements.txt        # Python dependencies
│   └── .env                    # Environment variables
│
├── frontend/
│   ├── ambulance-portal/       # React + Vite (Ambulance UI)
│   │   └── src/
│   │       ├── App.jsx         # Main ambulance dashboard
│   │       ├── MapView.jsx     # Leaflet map with hospital markers
│   │       ├── api.js          # Axios API client
│   │       └── App.css         # Styles
│   │
│   ├── hospital-portal/        # React + Vite (Hospital UI)
│   │   └── src/
│   │       ├── App.jsx         # Hospital resource update form
│   │       ├── api.js          # Axios API client
│   │       └── App.css         # Styles
│   │
│   └── map_demo.html           # Standalone map demo page
│
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** and **npm**
- **PostgreSQL** (or a Supabase instance)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd AmbulanceSystem
```

### 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Configure Environment Variables

Create a `.env` file in the `backend/` directory:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_SERVER=your_server_host
POSTGRES_PORT=5432
POSTGRES_DB=postgres
```

#### Initialize the Database

Run the schema file against your PostgreSQL instance:

```bash
psql -h <host> -U <user> -d <dbname> -f db_schema.sql
```

> **Note:** The app also auto-creates tables and seeds mock data on startup via SQLAlchemy.

#### Start the Backend Server

```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at **http://localhost:8000**.  
Interactive docs (Swagger UI) at **http://localhost:8000/docs**.

### 3. Frontend Setup

#### Ambulance Portal

```bash
cd frontend/ambulance-portal

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env with your LocationIQ API key for map tiles

# Start dev server
npm run dev
```

Runs on **http://localhost:5173**.

#### Hospital Portal

```bash
cd frontend/hospital-portal

# Install dependencies
npm install

# Start dev server
npm run dev
```

Runs on **http://localhost:5174**.

### 4. Docker (Backend Only)

```bash
cd backend
docker build -t emergency-routing-api .
docker run -p 8000:8000 --env-file .env emergency-routing-api
```

---

## 📡 API Reference

All endpoints are organized by portal. Authentication is via the `X-Role` HTTP header.

### Authentication

| Header | Value | Access |
|--------|-------|--------|
| `X-Role` | `ambulance` | Ambulance portal endpoints |
| `X-Role` | `hospital` | Hospital portal endpoints |
| `X-Role` | `admin` | All endpoints (superuser) |

> Missing or invalid `X-Role` header returns `401 Unauthorized` or `403 Forbidden`.

---

### 🚑 Ambulance Portal — `/api/ambulance`

#### `GET /api/ambulance/eligible-hospitals`

Find the top 3 hospitals ranked by a composite score.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `victim_lat` | `float` | ✅ | Latitude of the victim (-90 to 90) |
| `victim_lon` | `float` | ✅ | Longitude of the victim (-180 to 180) |
| `specialization` | `string` | ❌ | Required doctor specialization (e.g., `Cardiology`) |
| `severity` | `string` | ❌ | Case severity: `Low`, `Medium`, `High`, `Critical` |

**Response:** Array of hospital objects with `distance_km`, `freshness_score`, `confidence_level`, and buffered bed counts.

#### `GET /api/ambulance/offline-region`

Calculate a bounding box for offline map tile caching.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ambulance_lat` | `float` | ✅ | Ambulance latitude |
| `ambulance_lon` | `float` | ✅ | Ambulance longitude |
| `victim_lat` | `float` | ✅ | Victim latitude |
| `victim_lon` | `float` | ✅ | Victim longitude |
| `specialization` | `string` | ❌ | Required specialization |

**Response:** `{ min_lat, max_lat, min_lon, max_lon }` — bounding box with ~1.1 km margin.

#### `POST /api/ambulance/send-alert`

Broadcast an alert to hospitals and confirm assignment.

```json
{
  "case_id": 1,
  "hospital_ids": [1, 2, 3]
}
```

**Response:** Confirmation with assigned hospital details.

#### `POST /api/ambulance/process-case`

AI-powered case triage using a rule-based NLP engine.

```json
{
  "description": "Severe chest pain, suspected cardiac arrest"
}
```

**Response:** `{ "specialization": "Cardiology", "severity": "Critical" }`

---

### 🏥 Hospital Portal — `/api/hospital`

#### `POST /api/hospital/update-resources-range`

Report bed/ICU availability using range-based input.

```json
{
  "hospital_id": 1,
  "icu_range": "6-10",
  "beds_range": "10+"
}
```

**Supported ranges:** `"0-2"`, `"3-5"`, `"6-10"`, `"10+"`  
The system converts these to **conservative minimums** (e.g., `"6-10"` → stores `6`).

---

### 🔧 Admin Portal — `/api/admin`

#### `POST /api/admin/create-hospital`

Register a new hospital in the system.

```json
{
  "name": "City General Hospital",
  "latitude": 12.9716,
  "longitude": 77.5946,
  "tier_level": "Tier 1",
  "icu_available": 10,
  "emergency_beds": 25,
  "specialization": "Cardiology, Trauma, General Surgery"
}
```

---

### Utility Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Welcome message |
| `GET` | `/health` | Health check (`{ "status": "ok" }`) |

---

## 🧠 Ranking Algorithm

Hospitals are ranked using a **composite scoring formula**:

```
Score = (ICU_Score × 0.4) + (Beds_Score × 0.3) + (Freshness × 0.2) − (Distance_km × 0.1)
```

| Factor | Weight | Description |
|--------|--------|-------------|
| **ICU Score** | 40% | Bucketed score from bed range (`0-2` → 1, `3-5` → 2, `6-10` → 3, `10+` → 4) |
| **Beds Score** | 30% | Same bucketing as ICU |
| **Freshness** | 20% | Decay score based on `last_updated` timestamp |
| **Distance** | 10% | Haversine distance in kilometers (penalizes farther hospitals) |

### Safety Mechanisms

- **Conservative minimums** — Ranges are parsed to their lowest bound
- **Safety buffers** — Additional buffer subtracted during ranking
- **Freshness decay** — Stale data is automatically deprioritized
- **Confidence levels** — `HIGH` / `MEDIUM` / `LOW` based on data age
- **Threshold filtering** — Hospitals with ICU or Beds score < 2.0 are excluded

---

## 🗄️ Database Schema

The system uses **PostgreSQL** with the following tables:

| Table | Description |
|-------|-------------|
| `hospitals` | Core hospital identity (name, location, tier level) |
| `hospital_resources` | Bed/ICU availability with `last_updated` timestamps |
| `doctor_availabilities` | Per-hospital doctor specializations and status |
| `emergency_cases` | Logged emergency cases with status tracking |

Mock data includes 5 real Bangalore hospitals (Apollo, Fortis, Manipal, St. John's, Narayana Health).

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend Framework** | FastAPI (Python 3.11) |
| **ORM** | SQLAlchemy |
| **Database** | PostgreSQL (Supabase-hosted) |
| **Migrations** | Alembic |
| **Frontend** | React 19 + Vite |
| **Maps** | Leaflet + React-Leaflet + LocationIQ tiles |
| **HTTP Client** | Axios |
| **Containerization** | Docker |
| **Settings** | Pydantic Settings (`.env` based) |

---

## 🔒 Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|----------|-------------|
| `POSTGRES_USER` | PostgreSQL username |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_SERVER` | Database host |
| `POSTGRES_PORT` | Database port (default: `5432`) |
| `POSTGRES_DB` | Database name |

### Ambulance Portal (`frontend/ambulance-portal/.env`)

| Variable | Description |
|----------|-------------|
| `VITE_LOCATIONIQ_KEY` | API key for LocationIQ map tiles |

---

## 📄 License

This project is developed for educational and hackathon purposes.
