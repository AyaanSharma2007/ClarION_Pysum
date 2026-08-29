"""
Entity extraction service — classifies RFI text into a category.

Current state: STUB — always returns None so the record is still
stored and searchable; Layer 3 can backfill the category field
via its own Neo4j-connected pipeline.

To activate Claude API extraction:
  1. pip install anthropic
  2. Set EXTRACTION_BACKEND=claude and ANTHROPIC_API_KEY=sk-ant-... in .env
  3. The _extract_via_claude method below handles the rest automatically.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """
    Result returned by ExtractionService.extract().

    category: one of Statistics | IMPD Safety | Informed Consent |
              Protocol Design | Administrative | Other — or None if
              the stub backend is active.

    Layer 3 may add additional fields here (e.g. detected_themes) when
    it extends this service with its own NLP pipeline.
    """

    category: Optional[str] = None


class ExtractionService:
    """
    Config-flag-gated extraction service.
    Swap EXTRACTION_BACKEND in .env without touching any router code.
    """

    VALID_CATEGORIES = [
        "Statistics",
        "IMPD Safety",
        "Informed Consent",
        "Protocol Design",
        "Administrative",
        "Other",
    ]

    def __init__(self) -> None:
        self._backend = settings.EXTRACTION_BACKEND

    async def extract(self, rfi_text: str) -> ExtractionResult:
        """
        Extract structured entities from raw RFI text.

        Args:
            rfi_text: Concatenated consideration response texts (or full PDF text).

        Returns:
            ExtractionResult with category populated (or None for stub).
        """
        if self._backend == "stub":
            logger.debug("ExtractionService (stub): skipping extraction.")
            return ExtractionResult()

        if self._backend == "claude":
            return await self._extract_via_claude(rfi_text)

        raise ValueError(f"Unknown EXTRACTION_BACKEND: {self._backend!r}")

    async def _extract_via_claude(self, rfi_text: str) -> ExtractionResult:
        """
        Call Anthropic Claude to classify the RFI.
        Only reachable when EXTRACTION_BACKEND=claude and ANTHROPIC_API_KEY is set.
        """
        if not settings.ANTHROPIC_API_KEY:
            raise ValueError(
                "EXTRACTION_BACKEND=claude requires ANTHROPIC_API_KEY in .env"
            )

        try:
            import anthropic  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "Install anthropic: pip install anthropic"
            ) from exc

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        categories_str = " | ".join(self.VALID_CATEGORIES)
        prompt = (
            f"You are an EU CTR regulatory specialist.\n"
            f"Classify the following RFI text into exactly one category "
            f"from this list: {categories_str}.\n\n"
            f"RFI Text:\n{rfi_text[:3000]}\n\n"
            f'Respond with JSON only: {{"category": "<category>"}}'
        )

        message = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )

        try:
            data = json.loads(message.content[0].text)
            category = data.get("category")
            if category not in self.VALID_CATEGORIES:
                logger.warning(
                    "Claude returned unexpected category %r — defaulting to 'Other'",
                    category,
                )
                category = "Other"
            return ExtractionResult(category=category)
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.error("Failed to parse Claude response: %s", exc)
            return ExtractionResult()


# Module-level singleton.
extraction_service = ExtractionService()
