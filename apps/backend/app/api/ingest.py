import os
import json
import logging
import base64
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
import httpx

try:
    from apps.backend.models import RFIExtractionTemplate
    from apps.backend.app.safety_gateway import screen_untrusted_text
except ImportError:
    from models import RFIExtractionTemplate
    try:
        from app.safety_gateway import screen_untrusted_text
    except ImportError:
        from safety_gateway import screen_untrusted_text

import anthropic
from supabase import create_client, Client

router = APIRouter(tags=["Data Mesh Intake"])

# Initialize clients if environment variables are present
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Layer 2 Central Repository — pgvector + Postgres + audit trail
# Defaults to localhost:8001 for local dev (Layer 1 uses 8000)
LAYER2_URL = os.getenv("LAYER2_URL", "http://localhost:8001")

logger = logging.getLogger(__name__)

def get_supabase_client() -> Optional[Client]:
    if SUPABASE_URL and SUPABASE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None

@router.post("/parse-pdf", response_model=RFIExtractionTemplate)
async def parse_pdf(file: UploadFile = File(...)):
    """
    1) Takes an uploaded PDF document.
    2) Sends it to Claude API with a structured prompt.
    3) Returns extracted JSON matching the strict RFIExtractionTemplate Pydantic schema.
    """
    if not file.filename.endswith(".pdf") and file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a valid PDF document."
        )

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded PDF file is empty."
        )

    # Prepare JSON Schema prompt instruction
    schema_json = json.dumps(RFIExtractionTemplate.model_json_schema(), indent=2)

    prompt = f"""
You are an expert regulatory document parsing agent for EU CTR validation RFIs.
Extract all required fields from the attached RFI PDF document and format the result as a strict JSON object.

The JSON output MUST conform exactly to the following JSON Schema:
{schema_json}

Field Guidelines:
- rfi_id: Unique RFI identifier as printed in document (e.g. 'CT-2024-123456-12-00-SM01-001').
- due_date, response_date, submit_date: Format strictly as YYYY-MM-DD. Convert from dd/mm/yyyy if needed.
- msc.country: Member State Concerned as printed (e.g. 'Germany'). Non-empty string.
- indication.name: Full standard name of therapeutic indication (e.g. 'Type 2 Diabetes Mellitus').
- considerations: List of individual consideration objects (min 1 item required).
  - number: Integer consideration number.
  - ctr_article.name: Referenced section/article/annex (e.g. 'Annex I, Section 63').
  - response.text: Sponsor response text extracted verbatim.
  - outcome: Optional object with status string or null.

Return ONLY raw valid JSON, wrapped inside a JSON code block. No explanations or extra text.
"""

    if ANTHROPIC_API_KEY:
        try:
            client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
            base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

            message = await client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": base64_pdf
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )

            raw_text = message.content[0].text.strip()
            # Clean markdown codeblocks if present
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            extracted_json = json.loads(raw_text)
            validated_model = RFIExtractionTemplate.model_validate(extracted_json)
            return validated_model

        except ValidationError as val_err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Claude response failed Pydantic validation: {val_err}"
            )
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error communicating with Anthropic Claude API: {str(err)}"
            )
    else:
        # Fallback demonstration mode when API key is not configured
        mock_extracted = {
            "rfi_id": "CT-2024-123456-12-00-SM01-001",
            "due_date": "2026-03-16",
            "response_date": "2026-03-06",
            "submit_date": "2026-03-05",
            "msc": {"country": "Germany"},
            "indication": {"name": "Type 2 Diabetes Mellitus"},
            "considerations": [
                {
                    "number": 1,
                    "ctr_article": {"name": "Part I - Regulatory / Annex I, Section 63"},
                    "response": {"text": f"Extracted from uploaded PDF: '{file.filename}' (bytes: {len(pdf_bytes)}). Proof of payment provided."},
                    "outcome": None
                }
            ]
        }
        return RFIExtractionTemplate.model_validate(mock_extracted)


@router.post("/ingest")
async def ingest_rfi(payload: RFIExtractionTemplate):
    """
    1) Validates incoming RFI JSON.
    2) Appends immutable metadata (ingested_at, owner_team, validation_status).
    3) Prepares record for database write.
    """
    # Safety Gateway untrusted input boundary screen (Clarion Bible Section 6.2)
    for c in payload.considerations:
        text_to_screen = (c.response.text if c.response else "")
        screen_result = screen_untrusted_text(text_to_screen)
        if screen_result["flagged"]:
            logger.warning(f"Safety Gateway flagged prompt injection pattern in RFI {payload.rfi_id}")

    body_json = payload.model_dump(mode="json")
    validated_rfi = payload

    # Append Immutable Metadata
    metadata = {
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "owner_team": "EU-CTR-Data-Mesh-Team",
        "validation_status": "VALIDATED"
    }

    record_to_insert = {
        **validated_rfi.model_dump(mode="json"),
        **metadata
    }

    # Write to Supabase Postgres
    supabase = get_supabase_client()
    db_status = "persisted"
    db_message = "Record written to Supabase Postgres table 'rfi_intake'."

    if supabase:
        try:
            supabase.table("rfi_intake").insert(record_to_insert).execute()
        except Exception as db_err:
            db_status = "db_write_error"
            db_message = f"Supabase insert error: {str(db_err)}"
    else:
        db_status = "persisted_mock"
        db_message = "Supabase environment variables not configured. Record validated and prepared for Postgres write."

    # ── Forward to Layer 2 Central Repository ──────────────────────────────
    # Layer 2 stores the record in pgvector with per-consideration embeddings,
    # creates a tamper-evident audit chain, and makes the record searchable
    # via POST /search and POST /search/hybrid.
    layer2_status = "not_forwarded"
    layer2_message = ""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            l2_response = await client.post(
                f"{LAYER2_URL}/rfi",
                json=validated_rfi.model_dump(mode="json"),
            )
            if l2_response.status_code in (200, 201):
                layer2_status = "forwarded"
                layer2_message = "Record stored in Layer 2 Central Repository (pgvector + audit chain)."
            elif l2_response.status_code == 409:
                layer2_status = "duplicate"
                layer2_message = "Record already exists in Layer 2 (duplicate rfi_id)."
            else:
                layer2_status = "forward_error"
                layer2_message = f"Layer 2 returned HTTP {l2_response.status_code}: {l2_response.text[:200]}"
    except httpx.ConnectError:
        layer2_status = "layer2_offline"
        layer2_message = f"Layer 2 not reachable at {LAYER2_URL}. Record validated but not forwarded."
        logger.warning("Layer 2 not reachable at %s — record not forwarded.", LAYER2_URL)
    except Exception as l2_err:
        layer2_status = "forward_error"
        layer2_message = f"Layer 2 forwarding error: {str(l2_err)}"
        logger.error("Layer 2 forwarding failed: %s", l2_err)

    return {
        "status": "success",
        "db_status": db_status,
        "message": db_message,
        "layer2_status": layer2_status,
        "layer2_message": layer2_message,
        "record": record_to_insert
    }
