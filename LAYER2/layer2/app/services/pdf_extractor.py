"""
Layer 1 — Local PDF Extraction Service (Bible §4, §13).

Parses raw RFI PDFs into the canonical JSON schema using deterministic
local tools — no external API calls, respecting the confidentiality boundary.

Pipeline:
  1. pdfplumber extracts text from text-based PDFs
  2. pytesseract (OCR) fallback for scanned/image-based PDFs
  3. Regex-based deterministic parser extracts structured fields
  4. Returns a dict conforming to rfi_extraction_schema.json
"""
from __future__ import annotations

import io
import logging
import re
from datetime import datetime
from typing import Any, Optional

import pdfplumber

logger = logging.getLogger(__name__)


# ─── Text Extraction ─────────────────────────────────────────────────────────


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract text from a PDF using pdfplumber.
    Falls back to pytesseract OCR if pdfplumber returns no meaningful text.
    """
    text_pages: list[str] = []

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_pages.append(page_text)
    except Exception as exc:
        logger.warning("pdfplumber failed: %s — attempting OCR fallback", exc)

    full_text = "\n".join(text_pages).strip()

    # If pdfplumber returned essentially nothing, try OCR
    if len(full_text) < 50:
        logger.info("pdfplumber returned minimal text (%d chars) — trying OCR fallback", len(full_text))
        full_text = _ocr_fallback(pdf_bytes)

    return full_text


def _ocr_fallback(pdf_bytes: bytes) -> str:
    """
    OCR fallback using pytesseract + pdf2image.
    Only called when pdfplumber fails to extract meaningful text.
    """
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
    except ImportError:
        logger.error(
            "OCR fallback requires pytesseract and pdf2image. "
            "Install with: pip install pytesseract pdf2image"
        )
        return ""

    try:
        images = convert_from_bytes(pdf_bytes, dpi=300)
        ocr_pages = []
        for i, img in enumerate(images):
            page_text = pytesseract.image_to_string(img, lang="eng")
            ocr_pages.append(page_text)
            logger.debug("OCR page %d: %d chars", i + 1, len(page_text))
        return "\n".join(ocr_pages).strip()
    except Exception as exc:
        logger.error("OCR fallback failed: %s", exc)
        return ""


# ─── Deterministic Field Parser ──────────────────────────────────────────────


# Date patterns commonly found in EU CTR documents
_DATE_PATTERNS = [
    # YYYY-MM-DD
    r"(\d{4}-\d{2}-\d{2})",
    # DD/MM/YYYY
    r"(\d{2}/\d{2}/\d{4})",
    # DD.MM.YYYY
    r"(\d{2}\.\d{2}\.\d{4})",
]

# RFI ID pattern — EU CTR format
_RFI_ID_PATTERN = re.compile(
    r"(CT-\d{4}-\d{4,8}-\d{2}-\d{2}-[A-Z]{2}\d{2}-\d{3})",
    re.IGNORECASE,
)

# Consideration block markers
_CONSIDERATION_PATTERN = re.compile(
    r"Consideration\s+(?:number|no\.?|#)?\s*[:.]?\s*(\d+)",
    re.IGNORECASE,
)

# CTR Article references
_CTR_ARTICLE_PATTERN = re.compile(
    r"((?:Part\s+[IV]+\s*[-–—]?\s*)?(?:Annex\s+[IVX]+|Article)\s*,?\s*(?:Section\s+)?\d+(?:\.\d+)*)",
    re.IGNORECASE,
)

# Country names commonly appearing as MSC in EU CTR docs
_EU_COUNTRIES = [
    "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czech Republic",
    "Czechia", "Denmark", "Estonia", "Finland", "France", "Germany", "Greece",
    "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg",
    "Malta", "Netherlands", "Poland", "Portugal", "Romania", "Slovakia",
    "Slovenia", "Spain", "Sweden", "Norway", "Iceland",
]


def _parse_date(text: str) -> Optional[str]:
    """Try to find and normalize a date string to YYYY-MM-DD format."""
    for pattern in _DATE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            raw = match.group(1)
            # Already YYYY-MM-DD
            if re.match(r"\d{4}-\d{2}-\d{2}$", raw):
                return raw
            # DD/MM/YYYY or DD.MM.YYYY
            for fmt in ("%d/%m/%Y", "%d.%m.%Y"):
                try:
                    dt = datetime.strptime(raw, fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue
    return None


def _extract_labeled_date(text: str, label: str) -> Optional[str]:
    """Extract a date that appears after a specific label."""
    pattern = re.compile(
        rf"(?:{label})\s*[:.]?\s*(.{{10,30}})",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if match:
        snippet = match.group(1)
        if isinstance(snippet, str):
            return _parse_date(snippet)
    return None


def _extract_msc_country(text: str) -> str:
    """Extract the Member State Concerned country name."""
    # Look for explicit MSC label
    msc_pattern = re.compile(
        r"(?:Member\s+State\s+Concerned|MSC|Concerned\s+Member\s+State)\s*[:.]?\s*(\w[\w\s]{2,30})",
        re.IGNORECASE,
    )
    match = msc_pattern.search(text)
    if match:
        candidate = match.group(1).strip()
        for country in _EU_COUNTRIES:
            if country.lower() in candidate.lower():
                return country

    # Fallback: scan full text for EU country names
    for country in _EU_COUNTRIES:
        if re.search(rf"\b{re.escape(country)}\b", text, re.IGNORECASE):
            return country

    return "Unknown"


def _extract_indication(text: str) -> str:
    """Extract therapeutic indication."""
    ind_pattern = re.compile(
        r"(?:Indication|Therapeutic\s+(?:area|indication)|Disease)\s*[:.]?\s*(.{5,100})",
        re.IGNORECASE,
    )
    match = ind_pattern.search(text)
    if match:
        raw = match.group(1).strip()
        # Take up to the first newline or period-followed-by-space
        raw = re.split(r"[\n\r]|(?<=\.)\s", raw)[0].strip()
        return raw

    return "Unknown"


def _extract_considerations(text: str, rfi_id: str) -> list[dict[str, Any]]:
    """
    Extract individual consideration blocks from the RFI text.
    Each block typically has a number, a CTR article reference,
    and a sponsor response.
    """
    considerations: list[dict[str, Any]] = []

    # Find all consideration number markers and their positions
    markers = list(_CONSIDERATION_PATTERN.finditer(text))

    if not markers:
        # If no explicit markers, treat the whole text as a single consideration
        article_match = _CTR_ARTICLE_PATTERN.search(text)
        article_name = article_match.group(0) if article_match else "Not specified"

        # Try to find response text
        response_pattern = re.compile(
            r"(?:Sponsor\s+(?:response|reply)|Response)\s*[:.]?\s*(.+?)(?=\n\n|\Z)",
            re.IGNORECASE | re.DOTALL,
        )
        resp_match = response_pattern.search(text)
        response_text = resp_match.group(1).strip() if resp_match else text[:500]

        considerations.append({
            "number": 1,
            "ctr_article": {"name": article_name},
            "response": {"text": response_text},
            "outcome": None,
        })
        return considerations

    # Process each consideration block
    for i, marker in enumerate(markers):
        number = int(marker.group(1))
        start = marker.start()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        block = text[start:end]

        # Extract CTR article from this block
        article_match = _CTR_ARTICLE_PATTERN.search(block)
        article_name = article_match.group(0) if article_match else "Not specified"

        # Extract response text from this block
        response_pattern = re.compile(
            r"(?:Sponsor\s+(?:response|reply)|Response)\s*[:.]?\s*(.+?)(?=Consideration|$)",
            re.IGNORECASE | re.DOTALL,
        )
        resp_match = response_pattern.search(block)
        if resp_match:
            response_text = resp_match.group(1).strip()
        else:
            # Fallback: take text after the consideration header
            header_end = marker.end()
            response_text = block[header_end - start:].strip()[:1000]

        # Extract concern text (the question/issue raised)
        concern_pattern = re.compile(
            r"(?:Concern|Question|Issue|Comment)\s*[:.]?\s*(.+?)(?=(?:Sponsor\s+(?:response|reply)|Response)|$)",
            re.IGNORECASE | re.DOTALL,
        )
        concern_match = concern_pattern.search(block)
        concern_text = concern_match.group(1).strip() if concern_match else None

        considerations.append({
            "number": number,
            "ctr_article": {"name": article_name},
            "response": {"text": response_text},
            "outcome": None,
        })

    return considerations


def parse_rfi_fields(raw_text: str) -> dict[str, Any]:
    """
    Deterministic regex-based parser that extracts structured fields
    from raw RFI PDF text.

    Returns a dict conforming to rfi_extraction_schema.json.
    """
    # RFI ID
    rfi_id_match = _RFI_ID_PATTERN.search(raw_text)
    rfi_id = rfi_id_match.group(1) if rfi_id_match else f"CT-UNKNOWN-{id(raw_text)}"

    # Dates
    due_date = _extract_labeled_date(raw_text, "due date|deadline|response deadline")
    response_date = _extract_labeled_date(raw_text, "response date|date of response")
    submit_date = _extract_labeled_date(raw_text, "submit date|submission date|date of submission")

    # MSC and indication
    msc_country = _extract_msc_country(raw_text)
    indication = _extract_indication(raw_text)

    # Considerations
    considerations = _extract_considerations(raw_text, rfi_id)

    return {
        "rfi_id": rfi_id,
        "due_date": due_date,
        "response_date": response_date,
        "submit_date": submit_date,
        "msc": {"country": msc_country},
        "indication": {"name": indication},
        "considerations": considerations,
    }


def extract_rfi_from_pdf(pdf_bytes: bytes) -> dict[str, Any]:
    """
    End-to-end local PDF extraction pipeline.

    1. Extract raw text (pdfplumber → OCR fallback)
    2. Parse structured fields via regex
    3. Return canonical JSON dict

    No external API calls — fully local, confidentiality-safe.
    """
    logger.info("Starting local PDF extraction (pdfplumber + regex parser)...")

    raw_text = extract_text_from_pdf(pdf_bytes)
    if not raw_text:
        raise ValueError("Could not extract any text from the PDF (both pdfplumber and OCR failed).")

    logger.info("Extracted %d characters of text from PDF", len(raw_text))

    result = parse_rfi_fields(raw_text)

    logger.info(
        "Parsed RFI %s: %d considerations, MSC=%s",
        result["rfi_id"],
        len(result["considerations"]),
        result["msc"]["country"],
    )

    return result
