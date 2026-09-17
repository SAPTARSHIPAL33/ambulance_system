from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine
from app.core.seed import seed_database
from app.core.config import settings

# Role-based portal routers
from app.api.ambulance import router as ambulance_router
from app.api.hospital import router as hospital_router
from app.api.admin import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema
    Base.metadata.create_all(bind=engine)
    # Seed mock data into the database
    seed_database()
    yield


# =============================================
# Swagger UI Tag Descriptions
# =============================================
tags_metadata = [
    {
        "name": "Ambulance",
        "description": "**Ambulance Portal** — Dispatch & routing endpoints. "
                       "Find eligible hospitals, calculate offline regions, "
                       "send alerts, and triage cases. "
                       "Requires `X-Role: ambulance` header.",
    },
    {
        "name": "Hospital",
        "description": "**Hospital Portal** — Resource management endpoints. "
                       "Hospitals report bed/ICU availability as ranges. "
                       "Requires `X-Role: hospital` header.",
    },
    {
        "name": "Admin",
        "description": "**Admin Portal** — System administration endpoints. "
                       "Create hospitals and manage system-level data. "
                       "Requires `X-Role: admin` header.",
    },
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Real-Time Emergency Hospital Routing System API.\n\n"
        "Three role-based portals:\n"
        "- **Ambulance** — Dispatch & routing\n"
        "- **Hospital** — Resource updates\n"
        "- **Admin** — System management\n\n"
        "Set the `X-Role` header to `ambulance`, `hospital`, or `admin` to authenticate."
    ),
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

# =============================================
# CORS — allow React frontend to call the API
# =============================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================
# Register Portal Routers
# =============================================
app.include_router(ambulance_router, prefix="/api/ambulance", tags=["Ambulance"])
app.include_router(hospital_router, prefix="/api/hospital", tags=["Hospital"])
app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])


@app.get("/health")
def health_check():
    return {"status": "ok", "app_name": settings.PROJECT_NAME}


@app.get("/")
def root():
    return {"message": "Welcome to the Emergency Hospital Routing System API"}
