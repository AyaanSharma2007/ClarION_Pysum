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

from LAYER2.layer2.app.config import settings

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

        if self._backend == "ollama" or self._backend == "local":
            return await self._extract_via_ollama(rfi_text)

        raise ValueError(f"Unknown EXTRACTION_BACKEND: {self._backend!r}")

    async def _extract_via_ollama(self, rfi_text: str) -> ExtractionResult:
        """
        Call local Ollama endpoint (Llama 3.1 / Qwen2.5) to classify RFI text into JSON.
        Reachable when EXTRACTION_BACKEND=ollama or EXTRACTION_BACKEND=local.
        """
        import httpx

        ollama_url = getattr(settings, "OLLAMA_HOST", "http://localhost:11434")
        ollama_model = getattr(settings, "OLLAMA_MODEL", "llama3.1")

        logger.info("🤖 Routing RFI text to local Llama 3.1 via Ollama (%s, model=%s)...", ollama_url, ollama_model)

        categories_str = " | ".join(self.VALID_CATEGORIES)
        prompt = (
            f"You are an EU CTR regulatory specialist.\n"
            f"Classify the following RFI text into exactly one category "
            f"from this list: {categories_str}.\n\n"
            f"RFI Text:\n{rfi_text[:3000]}\n\n"
            f'Respond with valid JSON only: {{"category": "<category>"}}'
        )

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(
                    f"{ollama_url}/api/generate",
                    json={
                        "model": ollama_model,
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                    },
                )
                if res.status_code == 200:
                    response_json = res.json()
                    response_text = response_json.get("response", "{}")
                    data = json.loads(response_text)
                    category = data.get("category")
                    if category not in self.VALID_CATEGORIES:
                        category = "Other"
                    logger.info("✅ Llama 3.1 successfully extracted category: %r", category)
                    return ExtractionResult(category=category)
                else:
                    logger.error("Ollama HTTP %d: %s", res.status_code, res.text)
        except Exception as exc:
            logger.error("Failed to connect or parse Ollama response: %s", exc)

        return ExtractionResult(category="Other")



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
