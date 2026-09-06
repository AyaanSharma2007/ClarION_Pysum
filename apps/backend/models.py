from datetime import date
from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


def _validate_non_empty_string(value: str, field_name: str) -> str:
    """Helper to enforce strict non-null, non-empty, non-whitespace string naming."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{field_name}' strictly requires a non-null, non-empty standard string.")
    return value.strip()


class MSC(BaseModel):
    """Member State Concerned node representation."""
    country: str = Field(
        ...,
        description="The Member State Concerned as printed, e.g. 'Germany'. Maps to MSC.country merge key.",
        min_length=1
    )

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        return _validate_non_empty_string(v, "msc.country")


class Indication(BaseModel):
    """Therapeutic indication node representation."""
    name: str = Field(
        ...,
        description="Therapeutic indication/disease, e.g. 'Type 2 Diabetes Mellitus'. Maps to Indication.name merge key.",
        min_length=1
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return _validate_non_empty_string(v, "indication.name")


class CTRArticle(BaseModel):
    """Referenced CTR article/section representation."""
    name: str = Field(
        ...,
        description="The section/article/annex referenced by this specific consideration, e.g. 'Annex I, Section 63'.",
        min_length=1
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return _validate_non_empty_string(v, "ctr_article.name")


class Response(BaseModel):
    """Sponsor response text representation."""
    text: str = Field(
        ...,
        description="The sponsor's response text for this consideration, extracted verbatim from the 'Sponsor response' field."
    )


class Outcome(BaseModel):
    """Validation outcome representation (optional at extraction time)."""
    status: Optional[str] = Field(
        default=None,
        description="e.g. 'accepted', 'follow-up-required', 'rejected'. Maps to Outcome.status."
    )


class Consideration(BaseModel):
    """Individual RFI Consideration block."""
    number: int = Field(
        ...,
        description="Maps to Consideration.number. Taken directly from document 'Consideration number' field."
    )
    concern_text: Optional[str] = Field(
        default=None,
        description="The NCA's question or concern text — the actual RFI question raised by the authority. Maps to Consideration.concern_text."
    )
    ctr_article: CTRArticle = Field(
        ...,
        description="Maps to (Consideration)-[:REFERENCES]->(CTRArticle)."
    )
    response: Optional[Response] = Field(
        default=None,
        description="Maps to (Consideration)-[:HAS_RESPONSE]->(Response)."
    )
    outcome: Optional[Outcome] = Field(
        default=None,
        description="Maps to (Consideration)-[:STATUS]->(Outcome)."
    )


class RFIExtractionTemplate(BaseModel):
    """
    Pydantic v2 model for EU CTR Validation RFI Extraction Template.
    Strictly converted from schemas/rfi_extraction_schema.json.
    """
    model_config = {
        "populate_by_name": True,
        "str_strip_whitespace": True,
        "json_schema_extra": {
            "example": {
                "rfi_id": "CT-2024-123456-12-00-SM01-001",
                "due_date": "2026-03-16",
                "response_date": "2026-03-06",
                "submit_date": "2026-03-05",
                "msc": {"country": "Germany"},
                "indication": {"name": "Type 2 Diabetes Mellitus"},
                "considerations": [
                    {
                        "number": 1,
                        "concern_text": "Please provide evidence that...",
                        "ctr_article": {"name": "Part I - Regulatory / Annex I, Section 63"},
                        "response": None,
                        "outcome": None
                    }
                ]
            }
        }
    }

    @model_validator(mode='before')
    @classmethod
    def handle_string_objects(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if isinstance(data.get('msc'), str):
                data['msc'] = {'country': data['msc']}
            if isinstance(data.get('indication'), str):
                data['indication'] = {'name': data['indication']}
        return data

    rfi_id: str = Field(
        ...,
        description="Unique RFI identifier as printed in the document. Maps to RFI.rfi_id merge key.",
        min_length=1
    )
    due_date: Optional[date] = Field(
        default=None,
        description="Maps to RFI.due_date. Strict format: YYYY-MM-DD."
    )
    response_date: Optional[date] = Field(
        default=None,
        description="Maps to RFI.response_date. Strict format: YYYY-MM-DD."
    )
    submit_date: Optional[date] = Field(
        default=None,
        description="Maps to RFI.submit_date. Strict format: YYYY-MM-DD."
    )
    msc: MSC = Field(
        ...,
        description="Maps to (RFI)-[:SUBMITTED_TO]->(MSC)."
    )
    indication: Indication = Field(
        ...,
        description="Maps to (RFI)-[:INDICATION_TO]->(Indication)."
    )
    considerations: List[Consideration] = Field(
        ...,
        min_length=1,
        description="Array of distinct Consideration blocks. Requires at least 1 item."
    )

    @field_validator("rfi_id")
    @classmethod
    def validate_rfi_id(cls, v: str) -> str:
        return _validate_non_empty_string(v, "rfi_id")
