"""Evidence-grounded AI explanations for existing groundwater reports.

The LLM explains supplied analysis; it does not create or improve the underlying
hydrogeological prediction. Provider credentials remain server-side.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..settings import Settings
from .common import get_settings, limit_ai_requests

log = logging.getLogger("bwf.ai")
router = APIRouter()

_ALLOWED_FIELDS = {
    "status", "data_mode", "is_demo", "potential", "confidence", "factors",
    "evidence", "drilling_depth", "gaps", "recommendations", "warnings",
    "sources", "disclaimer", "generated_at",
}


def _safe_report(report: dict[str, Any]) -> dict[str, Any]:
    """Whitelist report fields and cap payload size; omit exact location identifiers."""
    safe = {k: report[k] for k in _ALLOWED_FIELDS if k in report}
    encoded = json.dumps(safe, ensure_ascii=False, default=str)
    if len(encoded) > 18000:
        raise HTTPException(status_code=413, detail="Report is too large to explain")
    return safe


class ExplainRequest(BaseModel):
    report: dict[str, Any] = Field(..., description="Existing analysis report returned by /api/analyze")
    language: str = Field(default="en", pattern="^(en|te)$")


def _build_prompt(report: dict[str, Any], language: str) -> str:
    lang = "Telugu" if language == "te" else "plain English"
    return (
        f"Explain this groundwater report in {lang} for a farmer. Use ONLY facts in the JSON. "
        "Separate measured evidence, model estimates, and missing information. Explain what the "
        "potential class and confidence mean; confidence is NOT probability of finding water. "
        "If is_demo is true or data_mode is demo, prominently say the data is synthetic and must "
        "not be used for drilling decisions. Never invent a yield, drilling depth, water level, "
        "success probability, source, date, or measurement. Do not infer that water is present. "
        "If evidence is missing, say it is unknown. Give practical next steps limited to the report's "
        "recommendations and gaps, including qualified hydrogeologist/geophysical review where "
        "appropriate. Keep the explanation concise, use headings and bullet points, and end with "
        "a clear statement that AI explanation does not validate or improve the underlying model.\n\n"
        f"REPORT JSON:\n{json.dumps(report, ensure_ascii=False, default=str)}"
    )


def _call_provider(settings: Settings, prompt: str) -> str:
    url = settings.ai_base_url.rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": settings.ai_model,
        "temperature": 0.1,
        "max_tokens": 650,
        "messages": [
            {"role": "system", "content": "You are a cautious groundwater report explainer. Never fabricate hydrogeological facts."},
            {"role": "user", "content": prompt},
        ],
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {settings.ai_api_key}",
        "Content-Type": "application/json",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = payload["choices"][0]["message"]["content"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Empty AI response")
        return text.strip()[:12000]
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError, json.JSONDecodeError) as exc:
        log.warning("AI explanation provider failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="AI explanation is temporarily unavailable") from exc


@router.post("/ai/explain", tags=["AI explanation"], dependencies=[Depends(limit_ai_requests)])
def explain_report(payload: ExplainRequest, settings: Settings = Depends(get_settings)):
    """Explain a report with a configured OpenAI-compatible model; no new prediction is made."""
    if not settings.ai_api_key:
        return {
            "status": "not_configured",
            "message": "AI is not configured. Set AI_API_KEY and AI_MODEL on the server.",
            "explanation": None,
        }
    report = _safe_report(payload.report)
    return {
        "status": "ok",
        "provider": settings.ai_provider,
        "model": settings.ai_model,
        "explanation": _call_provider(settings, _build_prompt(report, payload.language)),
        "notice": "AI explains the supplied report; it does not verify the data or improve prediction accuracy.",
    }
