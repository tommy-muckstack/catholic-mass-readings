#!/usr/bin/env python3
"""FastAPI wrapper that exposes catholic-mass-readings data over HTTP."""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, date as date_cls
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from catholic_mass_readings import models
from catholic_mass_readings.usccb import USCCB


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


app = FastAPI(
    title="Catholic Mass Readings API",
    description="Lightweight REST wrapper around the catholic-mass-readings scraper",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReadingText(BaseModel):
    type: str
    title: str
    reference: str
    content: str
    verses: List[Dict[str, Any]] = Field(default_factory=list)


class LiturgicalInfoResponse(BaseModel):
    date: str
    season: Optional[str] = ""
    seasonWeek: Optional[int] = None
    weekday: Optional[str] = ""
    primaryCelebration: Optional[Dict[str, Any]] = None
    liturgicalColor: Optional[str] = None
    seasonDisplayName: Optional[str] = ""


class DailyReadingResponse(BaseModel):
    id: str
    title: str
    description: str
    readingDate: str
    audioUrl: Optional[str] = None
    duration: Optional[str] = None
    author: str = "United States Conference of Catholic Bishops"
    subtitle: Optional[str] = None
    liturgicalInfo: Optional[LiturgicalInfoResponse] = None
    firstReading: Optional[ReadingText] = None
    responsorialPsalm: Optional[ReadingText] = None
    secondReading: Optional[ReadingText] = None
    gospel: Optional[ReadingText] = None
    hasTextContent: bool = True
    hasAudio: bool = False

def _parse_date(value: str) -> date_cls:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:  # pragma: no cover
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD") from exc

def _build_reading(section: Any, slug: str) -> Optional[ReadingText]:
    readings = getattr(section, "readings", None)
    if not readings:
        return None

    reference_parts: List[str] = []
    content_chunks: List[str] = []
    verses: List[Dict[str, Any]] = []

    for entry in readings:
        header = getattr(entry, "header", "")
        if header:
            reference_parts.append(header)

        text = getattr(entry, "text", "")
        if text:
            stripped = text.strip()
            if stripped:
                content_chunks.append(stripped)

        for verse in getattr(entry, "verses", []):
            verses.append({
                "text": verse.text,
                "link": verse.link,
                "book": verse.book,
            })

    content = "\n\n".join(content_chunks).strip()
    if not content:
        return None

    reference = "; ".join(part for part in reference_parts if part)
    display_title = getattr(section, "display_header", None) or getattr(section, "header", slug)

    return ReadingText(
        type=slug,
        title=display_title,
        reference=reference,
        content=content,
        verses=verses,
    )

def _slug_for_section(section: Any, *, first_taken: bool, second_taken: bool) -> Optional[str]:
    section_type = str(getattr(section, "type_", "")).lower()
    header = str(getattr(section, "header", "")).lower()

    if "gospel" in section_type or "gospel" in header:
        return "gospel"
    if "psalm" in section_type or "psalm" in header:
        return "responsorial_psalm"
    if "second" in section_type or "second" in header:
        return "second_reading"
    if "reading" in section_type or "reading" in header:
        return "second_reading" if first_taken and not second_taken else "first_reading"
    return None

def _build_liturgical_info(mass: Any, date_str: str) -> LiturgicalInfoResponse:
    title = getattr(mass, "title", "") or ""
    return LiturgicalInfoResponse(
        date=date_str,
        season="",
        seasonWeek=None,
        weekday=title,
        primaryCelebration=None,
        liturgicalColor=None,
        seasonDisplayName=title,
    )

def convert_mass_to_response(mass: Any) -> DailyReadingResponse:
    if mass is None:
        raise HTTPException(status_code=404, detail="No mass readings found")

    first_reading = None
    psalm = None
    second_reading = None
    gospel = None

    first_taken = False
    second_taken = False

    for section in getattr(mass, "sections", []):
        slug = _slug_for_section(section, first_taken=first_taken, second_taken=second_taken)
        if slug is None:
            continue

        reading = _build_reading(section, slug)
        if reading is None:
            continue

        if slug == "first_reading" and not first_taken:
            first_reading = reading
            first_taken = True
        elif slug == "second_reading" and not second_taken:
            second_reading = reading
            second_taken = True
        elif slug == "responsorial_psalm" and psalm is None:
            psalm = reading
        elif slug == "gospel" and gospel is None:
            gospel = reading

    mass_date = getattr(mass, "date", None)
    date_str = mass_date.isoformat() if isinstance(mass_date, date_cls) else datetime.now().date().isoformat()
    audio_url = getattr(mass, "podcast", None)
    if isinstance(audio_url, dict):
        audio_url = audio_url.get("url")

    response = DailyReadingResponse(
        id=getattr(mass, "url", f"usccb-{date_str}"),
        title=getattr(mass, "title", "Daily Mass Readings"),
        description=getattr(mass, "title", "Daily Mass readings from USCCB"),
        readingDate=date_str,
        audioUrl=audio_url,
        duration=None,
        author="United States Conference of Catholic Bishops",
        subtitle=getattr(mass, "title", None),
        liturgicalInfo=_build_liturgical_info(mass, date_str),
        firstReading=first_reading,
        responsorialPsalm=psalm,
        secondReading=second_reading,
        gospel=gospel,
    )
    response.hasAudio = bool(response.audioUrl)
    response.hasTextContent = any([first_reading, psalm, second_reading, gospel])
    return response


async def fetch_daily_reading(target_date: date_cls) -> DailyReadingResponse:
    async with USCCB() as usccb:
        mass = await usccb.get_mass_from_date(target_date)
        if mass is None:
            fallback_url = models.MassType.DEFAULT.to_url(target_date)
            logger.info(
                "Primary mass lookup returned none; trying fallback URL %s",
                fallback_url,
            )
            mass = await usccb.get_mass_from_url(fallback_url)
    if not mass:
        raise HTTPException(status_code=404, detail="No mass readings found")
    return convert_mass_to_response(mass)


@app.get("/")
async def root() -> Dict[str, Any]:
    return {
        "message": "Catholic Mass Readings API",
        "status": "active",
        "version": app.version,
    }


@app.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "healthy", "service": "catholic-mass-readings-api"}


@app.get("/debug")
async def debug_endpoint() -> Dict[str, Any]:
    """Debug endpoint to help diagnose deployment issues."""
    import sys
    
    debug_info = {
        "python_version": sys.version,
        "working_directory": os.getcwd(),
        "railway_environment": os.environ.get('RAILWAY_ENVIRONMENT', 'unknown'),
        "port": os.environ.get('PORT', 'not_set'),
    }
    
    # Test imports
    try:
        from catholic_mass_readings.usccb import USCCB as TestUSCCB
        from catholic_mass_readings import models as test_models
        debug_info["imports"] = "success"
    except Exception as e:
        debug_info["imports"] = f"failed: {str(e)}"
        return debug_info
    
    # Test USCCB functionality
    try:
        test_date = datetime.now().date()
        url = test_models.MassType.DEFAULT.to_url(test_date)
        debug_info["url_generation"] = {"date": test_date.isoformat(), "url": url}
        
        async with TestUSCCB() as usccb:
            mass = await usccb.get_mass_from_date(test_date)
            if mass:
                debug_info["scraper_test"] = {
                    "success": True,
                    "title": mass.title,
                    "sections_count": len(mass.sections),
                    "url": mass.url
                }
            else:
                debug_info["scraper_test"] = {"success": False, "error": "No mass found"}
                
    except Exception as e:
        debug_info["scraper_test"] = {"success": False, "error": str(e)}
    
    return debug_info


@app.get("/readings", response_model=DailyReadingResponse)
async def get_readings(date: str = Query(..., description="Date in YYYY-MM-DD format")) -> DailyReadingResponse:
    target_date = _parse_date(date)
    return await fetch_daily_reading(target_date)


@app.get("/readings/today", response_model=DailyReadingResponse)
async def get_today_readings() -> DailyReadingResponse:
    async with USCCB() as usccb:
        mass = await usccb.get_today_mass()
    if not mass:
        raise HTTPException(status_code=404, detail="No mass readings found")
    return convert_mass_to_response(mass)


@app.get("/readings/{date_str}", response_model=DailyReadingResponse)
async def get_readings_by_date(date_str: str) -> DailyReadingResponse:
    target_date = _parse_date(date_str)
    return await fetch_daily_reading(target_date)


@app.get("/readings/{date_str}/alternates")
async def get_alternate_readings(date_str: str) -> Dict[str, Any]:
    target_date = _parse_date(date_str)
    async with USCCB() as usccb:
        masses = await usccb.get_alternate_readings(target_date)

    responses = [convert_mass_to_response(mass) for mass in masses]
    return {
        "date": date_str,
        "alternate_readings": responses,
        "count": len(responses),
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    logger.info("Starting server on 0.0.0.0:%s", port)
    logger.info("Python version: %s", sys.version)
    logger.info("Environment: %s", os.environ.get('RAILWAY_ENVIRONMENT', 'development'))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
