"""Printable report: analysis dict -> HTML (Jinja2) -> PDF (WeasyPrint).

The HTML is self-contained so the browser can also print it ("Save as PDF") when WeasyPrint is not
installed on the server. Telugu needs a Telugu font on the machine that lays out the PDF; the Docker
image installs Noto/Lohit Telugu (see backend/Dockerfile).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .. import i18n

TEMPLATES = Path(__file__).parent / "templates"
IST = timezone(timedelta(hours=5, minutes=30))
LANGS = ("en", "te")


class PdfUnavailable(RuntimeError):
    """WeasyPrint (or its system libraries) is not installed."""


def _env() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html"]),
                       trim_blocks=True, lstrip_blocks=True)


def _txt(value: Any, lang: str) -> str:
    """{'en':..,'te':..} -> the chosen language (English fallback); plain strings pass through."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("en") or "")
    return str(value)


def format_ist(iso: Optional[str]) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST).strftime("%d %b %Y, %H:%M IST")


def fmt_date(iso: Optional[str]) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso).strftime("%d %b %Y")
    except ValueError:
        return iso


def render_report_html(analysis: dict, lang: str = "en") -> str:
    lang = lang if lang in LANGS else "en"

    def t(v):
        return _txt(v, lang)

    def L(key: str, **params) -> str:
        text = _txt(i18n.LABELS.get(key), lang) or key
        return text.format(**params) if params else text

    ctx = {"a": analysis, "lang": lang, "t": t, "L": L, "ist": format_ist, "fdate": fmt_date,
           "ok": analysis.get("status") == "ok",
           "demo": bool(analysis.get("is_demo"))}
    return _env().get_template("report.html").render(**ctx)


def html_to_pdf(html: str) -> bytes:
    try:
        from weasyprint import HTML  # imported lazily: needs Pango/Cairo system libraries
    except Exception as e:  # ImportError or OSError for missing system libs
        raise PdfUnavailable(str(e)) from e
    return HTML(string=html).write_pdf()
