from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response

from ..reports.render import PdfUnavailable, html_to_pdf, render_report_html
from ..services import Container, run_analysis
from .common import get_container, limit_requests

router = APIRouter(prefix="/report", tags=["report"], dependencies=[Depends(limit_requests)])

NO_STORE = {"Cache-Control": "no-store"}


def _html(c: Container, lat: float, lon: float, lang: str, accuracy_m: Optional[float]) -> str:
    return render_report_html(run_analysis(c, lat, lon, accuracy_m), lang)


@router.get("/html", response_class=HTMLResponse)
def report_html(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180),
                lang: Literal["en", "te"] = "en", accuracy_m: Optional[float] = Query(None, ge=0, le=1_000_000),
                c: Container = Depends(get_container)):
    """Printable report as HTML (the browser's 'Save as PDF' works as a fallback for /report/pdf)."""
    return HTMLResponse(_html(c, lat, lon, lang, accuracy_m), headers=NO_STORE)


@router.get("/pdf")
def report_pdf(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180),
               lang: Literal["en", "te"] = "en", accuracy_m: Optional[float] = Query(None, ge=0, le=1_000_000),
               c: Container = Depends(get_container)):
    """Downloadable PDF report (needs WeasyPrint on the server; otherwise 501 and the UI falls back to /report/html)."""
    html = _html(c, lat, lon, lang, accuracy_m)
    try:
        pdf = html_to_pdf(html)
    except PdfUnavailable:
        raise HTTPException(status_code=501, detail="pdf_unavailable")
    name = f"borewell-report_{lat:.4f}_{lon:.4f}_{lang}.pdf"
    return Response(pdf, media_type="application/pdf", headers={**NO_STORE, "Content-Disposition": f'attachment; filename="{name}"'})
