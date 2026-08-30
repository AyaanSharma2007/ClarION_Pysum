import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from apps.backend.models import RFIExtractionTemplate
    from apps.backend.app.api.ingest import router as ingest_router
except ImportError:
    from models import RFIExtractionTemplate
    from app.api.ingest import router as ingest_router

app = FastAPI(
    title="EU CTR RFI Data Mesh Intake API",
    description="Layer 1 Data Mesh Intake API for EU CTR validation RFI platform parsing and strict Pydantic v2 validation.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Ingest API Router
app.include_router(ingest_router)

class RFIResponse(BaseModel):
    id: str
    status: str
    message: str
    validated_payload: RFIExtractionTemplate

@app.get("/")
def read_root():
    return {
        "service": "EU CTR RFI Data Mesh Intake API",
        "status": "online",
        "layer": "Layer 1 (Data Mesh Intake)"
    }

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "backend": "FastAPI (Pydantic v2)",
        "integrations": {
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "supabase": bool(os.getenv("SUPABASE_URL"))
        }
    }

@app.post("/api/rfi/intake", response_model=RFIResponse)
async def submit_rfi(payload: RFIExtractionTemplate):
    """
    Intake RFI extraction payload, validate with Pydantic v2, and return structured mesh object.
    """
    try:
        return RFIResponse(
            id=payload.rfi_id,
            status="validated",
            message=f"RFI '{payload.rfi_id}' successfully validated against EU CTR Data Mesh schema.",
            validated_payload=payload
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
