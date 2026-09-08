import os
import json
import logging
import base64
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, BackgroundTasks, UploadFile, File, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
import httpx
import fitz  # PyMuPDF
from ..safety_gateway import screen_untrusted_text
from ..opa_client import check_governance
from ..audit import write_audit_event
from apps.backend.models import RFIExtractionTemplate

import anthropic
from supabase import create_client, Client

router = APIRouter(tags=["Data Mesh Intake"])

# Initialize clients if environment variables are present
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
EXTRACTION_BACKEND = os.getenv("EXTRACTION_BACKEND", "gemini")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")

# Layer 2 Central Repository — pgvector + Postgres + audit trail
# Defaults to localhost:8001 for local dev (Layer 1 uses 8000)
LAYER2_URL = os.getenv("LAYER2_URL", "http://localhost:8001")

logger = logging.getLogger(__name__)

# ── Neo4j credentials (optional — sync is skipped gracefully if not set) ──────
NEO4J_URI      = os.getenv("NEO4J_URI")
NEO4J_USER     = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")


def _sync_rfi_to_neo4j(rfi_payload: dict) -> None:
    """
    Background task: MERGE the freshly-ingested RFI into Neo4j.
    Called after a successful Layer 2 write. Safe to fail — errors are
    only logged, never surfaced to the user.
    """
    if not NEO4J_URI or not NEO4J_PASSWORD:
        logger.debug("Neo4j credentials not configured — skipping graph sync.")
        return

    try:
        from neo4j import GraphDatabase  # lazy import — only needed if configured
    except ImportError:
        logger.warning("neo4j package not installed — skipping graph sync.")
        return

    MERGE_QUERY = """
    MERGE (rfi:RFI {rfi_id: $rfi_id})
    SET rfi.due_date       = CASE WHEN $due_date IS NULL THEN null ELSE datetime($due_date + 'T00:00:00Z') END,
        rfi.response_date  = CASE WHEN $response_date IS NULL THEN null ELSE datetime($response_date + 'T00:00:00Z') END,
        rfi.submit_date    = CASE WHEN $submit_date IS NULL THEN null ELSE datetime($submit_date + 'T00:00:00Z') END,
        rfi.category       = $category

    MERGE (msc:MSC {msc_country: $msc_country})
    MERGE (rfi)-[:SUBMITTED_TO]->(msc)

    MERGE (ind:Indication {indication_name: $indication_name})
    MERGE (rfi)-[:INDICATION_TO]->(ind)

    WITH rfi
    UNWIND $considerations AS c
      MERGE (cons:Consideration {consideration_id: c.id})
      SET cons.consideration_number = c.number,
          cons.concern_text         = c.concern_text,
          cons.response_text        = c.response_text
      MERGE (rfi)-[:HAS_CONSIDERATION]->(cons)

      MERGE (art:CTR_Articles {ctr_article_name: c.ctr_article_name})
      MERGE (cons)-[:REFERENCES]->(art)

      FOREACH (_ IN CASE WHEN c.outcome_status IS NOT NULL THEN [1] ELSE [] END |
        MERGE (out:Outcome {outcome_status: c.outcome_status})
        MERGE (cons)-[:STATUS]->(out)
      )
    """

    # Build flat considerations list from nested RFIExtractionTemplate shape
    considerations = []
    for c in rfi_payload.get("considerations", []):
        considerations.append({
            "id":               f'{rfi_payload["rfi_id"]}-C{c.get("number", 1)}',
            "number":           c.get("number", 1),
            "concern_text":     c.get("concern_text") or c.get("text") or "",
            "ctr_article_name": (c.get("ctr_article") or {}).get("name") or "Unknown",
            "response_text":    (c.get("response") or {}).get("text") or c.get("response_text") or "",
            "outcome_status":   (c.get("outcome") or {}).get("status"),
        })

    params = {
        "rfi_id":          rfi_payload["rfi_id"],
        "due_date":        rfi_payload.get("due_date"),
        "response_date":   rfi_payload.get("response_date"),
        "submit_date":     rfi_payload.get("submit_date"),
        "category":        rfi_payload.get("category"),
        "msc_country":     (rfi_payload.get("msc") or {}).get("country") or "Unknown",
        "indication_name": (rfi_payload.get("indication") or {}).get("name") or "Unknown",
        "considerations":  considerations,
    }

    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session() as session:
            session.execute_write(lambda tx, p: tx.run(MERGE_QUERY, **p), params)
        driver.close()
        logger.info("Neo4j sync OK — %s", rfi_payload["rfi_id"])
    except Exception as e:
        logger.warning("Neo4j sync failed for %s: %s", rfi_payload.get("rfi_id"), e)


def get_supabase_client() -> Optional[Client]:
    if SUPABASE_URL and SUPABASE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None

@router.post("/parse-pdf", response_model=RFIExtractionTemplate)
async def parse_pdf(file: UploadFile = File(...)):
    """
    1) Takes an uploaded PDF document.
    2) Sends it to Gemini API (or Claude API) with a structured prompt.
    3) Returns extracted JSON matching the strict RFIExtractionTemplate Pydantic schema.
    """
    filename = file.filename or ""
    if not filename.endswith(".pdf") and file.content_type != "application/pdf":
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

CRITICAL FIRST STEP: SILENT CHECK
Evaluate the attached PDF. If it does not appear to be a genuine clinical trial regulatory document or RFI (e.g., if it is a random receipt, generic text, or unrelated document), you MUST immediately return exactly this JSON: {{"error": "try again"}} and NOTHING ELSE.

If it IS a valid RFI, extract all required fields and format the result as a strict JSON object.

IMPORTANT: We ONLY want the problems/concerns stated in the RFI by the NCA authority.
Do NOT extract the sponsor's response. Set the "response" field to null for every consideration.

The JSON output MUST conform exactly to the following JSON Schema:
{schema_json}

Field Guidelines:
- rfi_id: Unique RFI identifier as printed in document (do NOT use placeholder/mock data).
- due_date, response_date, submit_date: Format strictly as YYYY-MM-DD. Convert from dd/mm/yyyy if needed.
- msc.country: Member State Concerned as printed. Non-empty string.
- indication.name: Full standard name of therapeutic indication as printed (do NOT hallucinate or use mock data like 'Type 2 Diabetes Mellitus' if it's not actually in the text).
- considerations: List of individual consideration objects (min 1 item required).
  - number: Integer consideration number.
  - concern_text: CRITICAL — extract the NCA authority's question, concern, or objection text verbatim.
  - ctr_article.name: Referenced section/article/annex.
  - response: ALWAYS set to null.
  - outcome: Optional object with status string or null.

Return ONLY raw valid JSON, wrapped inside a JSON code block. No explanations or extra text.
"""

    if EXTRACTION_BACKEND == "gemini" and GEMINI_API_KEY:
        try:
            base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "inline_data": {
                                    "mime_type": "application/pdf",
                                    "data": base64_pdf
                                }
                            },
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "response_mime_type": "application/json"
                }
            }

            gemini_models = [
                os.getenv("GEMINI_MODEL", "gemini-3.7-flash"),
                "gemini-3.7-flash",
                "gemini-3.6-flash",
                "gemini-3.5-flash-lite",
            ]
            # Deduplicate preserving order
            seen = set()
            models_to_try = [m for m in gemini_models if not (m in seen or seen.add(m))]

            resp = None
            for model_name in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        break
                    elif resp.status_code == 404:
                        logger.warning("Model %s returned 404. Trying next model...", model_name)
                        continue
                    else:
                        break

            if resp is None or resp.status_code != 200:
                if resp and resp.status_code == 400 and "API_KEY_INVALID" in resp.text:
                    raise Exception("Gemini API key is invalid or revoked.")
                elif resp:
                    raise Exception(f"Gemini API HTTP {resp.status_code}: {resp.text}")
                else:
                    raise Exception("Failed to communicate with Gemini API.")
            else:
                res_data = resp.json()
                raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()

                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                raw_text = raw_text.strip()

                extracted_json = json.loads(raw_text)
                if extracted_json.get("error") == "try again":
                    raise HTTPException(status_code=400, detail="try again")
                validated_model = RFIExtractionTemplate.model_validate(extracted_json)
                return validated_model

        except ValidationError as val_err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="try again"
            )
        except HTTPException:
            raise
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error communicating with Gemini API: {str(err)}"
            )

    elif EXTRACTION_BACKEND == "anthropic" and ANTHROPIC_API_KEY:
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

            text_blocks = [
                getattr(block, "text", "") 
                for block in message.content 
                if getattr(block, "type", None) == "text" and hasattr(block, "text")
            ]
            if not text_blocks:
                raise Exception("No text block returned from Anthropic Claude response.")
            raw_text = text_blocks[0].strip()
            # Clean markdown codeblocks if present
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            extracted_json = json.loads(raw_text)
            if extracted_json.get("error") == "try again":
                raise HTTPException(status_code=400, detail="try again")
            validated_model = RFIExtractionTemplate.model_validate(extracted_json)
            return validated_model

        except ValidationError as val_err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="try again"
            )
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error communicating with Anthropic Claude API: {str(err)}"
            )
    elif EXTRACTION_BACKEND == "ollama":
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            pdf_text = ""
            for page in doc:
                pdf_text += page.get_text()
            
            ollama_prompt = f"{prompt}\n\nPDF TEXT:\n{pdf_text}"
            
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": ollama_prompt,
                "format": "json",
                "stream": False
            }
            
            url = f"{OLLAMA_HOST}/api/generate"
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(url, json=payload)
                
            if resp.status_code != 200:
                raise Exception(f"Ollama API HTTP {resp.status_code}: {resp.text}")
                
            res_data = resp.json()
            raw_text = res_data.get("response", "").strip()
            
            # Clean markdown codeblocks if present
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()
            
            extracted_json = json.loads(raw_text)
            if extracted_json.get("error") == "try again":
                raise HTTPException(status_code=400, detail="try again")
            validated_model = RFIExtractionTemplate.model_validate(extracted_json)
            return validated_model
            
        except ValidationError as val_err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="try again"
            )
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error communicating with Ollama API: {str(err)}"
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No valid extraction backend configured (check EXTRACTION_BACKEND in .env)."
        )


@router.post("/ingest")
async def ingest_rfi(payload: RFIExtractionTemplate, background_tasks: BackgroundTasks):
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
        "owner_team": "EU-Hub-Regulatory", # Updated to match OPA policy logic
        "validation_status": "VALIDATED"
    }

    record_to_insert = {
        **validated_rfi.model_dump(mode="json"),
        **metadata
    }

    # Governance Check (OPA)
    gov_violations = check_governance(
        request={"action": "write", "user_team": metadata["owner_team"]},
        rfis=[record_to_insert],
        responses=[]
    )
    if gov_violations:
        raise HTTPException(status_code=403, detail={"error": "Governance Violation", "violations": gov_violations})
        
    # Generate Audit Event
    audit_event = write_audit_event(
        record_id=payload.rfi_id,
        record_type="rfi_ingest",
        event_type="ingested",
        actor="System",
        payload=record_to_insert,
        prev_hash=None
    )

    # Write to Supabase Postgres
    supabase = get_supabase_client()

    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase is not configured. Set SUPABASE_URL and SUPABASE_KEY environment variables in apps/backend/.env"
        )

    try:
        supabase.table("rfi_intake").insert(record_to_insert).execute()
    except Exception as db_err:
        logger.error("Supabase insert failed: %s", db_err)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Supabase database write failed: {str(db_err)}"
        )

    db_status = "persisted"
    db_message = "Record written to Supabase Postgres table 'rfi_intake'."

    # ── Analytics Enrichment (Background) ──────────────────────────────────
    # Triggers: Qwen JSON extraction → embedding → pgvector similarity →
    # Neo4j Department/Category/IS_SIMILAR_TO relationships.
    # Runs as a background task so the ingest response stays fast.
    concern_texts = [
        c.concern_text for c in payload.considerations
        if c.concern_text
    ]
    if concern_texts:
        async def _run_analytics_enrichment():
            try:
                from apps.backend.app.analytics_enrichment import enrich_rfi_analytics
                analytics_result = await enrich_rfi_analytics(
                    rfi_id=payload.rfi_id,
                    concern_texts=concern_texts,
                    supabase_client=supabase,
                )
                logger.info(
                    "Analytics enrichment complete for %s: duplicate=%s, similar_count=%d",
                    payload.rfi_id,
                    analytics_result.get("is_duplicate"),
                    analytics_result.get("similar_count", 0),
                )
            except Exception as e:
                logger.warning("Analytics enrichment failed for %s: %s", payload.rfi_id, e)

        background_tasks.add_task(_run_analytics_enrichment)

    # ── Forward to Layer 2 Central Repository ──────────────────────────────
    # Layer 2 stores the record in pgvector with per-consideration embeddings,
    # creates a tamper-evident audit chain, and makes the record searchable
    # via POST /search and POST /search/hybrid.
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            l2_response = await client.post(
                f"{LAYER2_URL}/rfi",
                json=validated_rfi.model_dump(mode="json"),
            )
            if l2_response.status_code in (200, 201):
                layer2_status = "forwarded"
                layer2_message = "Record stored in Layer 2 Central Repository (pgvector + audit chain)."
                # Auto-sync to Neo4j in the background — transparent to the user
                background_tasks.add_task(_sync_rfi_to_neo4j, validated_rfi.model_dump(mode="json"))
            elif l2_response.status_code == 409:
                layer2_status = "duplicate"
                layer2_message = "Record already exists in Layer 2 (duplicate rfi_id)."
            else:
                logger.error("Layer 2 returned HTTP %s: %s", l2_response.status_code, l2_response.text[:200])
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Layer 2 returned HTTP {l2_response.status_code}: {l2_response.text[:200]}"
                )
    except HTTPException:
        raise
    except httpx.ConnectError:
        logger.error("Layer 2 not reachable at %s", LAYER2_URL)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Layer 2 is not reachable at {LAYER2_URL}. Ensure the Layer 2 service and its database are running."
        )
    except Exception as l2_err:
        logger.error("Layer 2 forwarding failed: %s", l2_err)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Layer 2 forwarding error: {str(l2_err)}"
        )

    return {
        "status": "success",
        "db_status": db_status,
        "message": db_message,
        "layer2_status": layer2_status,
        "layer2_message": layer2_message,
        "record": record_to_insert,
        "audit_event": audit_event
    }
