#!/usr/bin/env python3
"""FastAPI wrapper that exposes catholic-mass-readings data over HTTP."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, date as date_cls, timedelta
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
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
    version="1.2.0",
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

    # Skip "Verse Before the Gospel" / "Alleluia" — these are not the Gospel reading
    if "verse before" in header or "alleluia" in section_type or "alleluia" in header:
        return None
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


# Readings for a given date never change, but USCCB aggressively rate-limits
# per IP (a short burst earns a ~1 minute block), and all production traffic
# leaves Railway from one egress IP. Cache each date's response in memory and
# collapse concurrent fetches for the same date into a single upstream request.
READINGS_CACHE_TTL_SECONDS = 12 * 60 * 60
READINGS_CACHE_MAX_ENTRIES = 64

# When USCCB returns 403/429 the whole egress IP is blocked for roughly a
# minute; any request during that window both fails and extends our standing
# with their WAF. Back off globally instead of retrying per request.
UPSTREAM_COOLDOWN_SECONDS = 60

_readings_cache: Dict[str, Tuple[float, DailyReadingResponse]] = {}
_readings_locks: Dict[str, asyncio.Lock] = {}
_upstream_blocked_until = 0.0


def _cache_fresh(date_key: str) -> Optional[DailyReadingResponse]:
    cached = _readings_cache.get(date_key)
    if cached and time.monotonic() - cached[0] < READINGS_CACHE_TTL_SECONDS:
        return cached[1]
    return None


def _cache_store(date_key: str, response: DailyReadingResponse) -> None:
    _readings_cache[date_key] = (time.monotonic(), response)
    while len(_readings_cache) > READINGS_CACHE_MAX_ENTRIES:
        oldest_key = min(_readings_cache, key=lambda k: _readings_cache[k][0])
        _readings_cache.pop(oldest_key, None)
        _readings_locks.pop(oldest_key, None)


async def fetch_daily_reading(target_date: date_cls) -> DailyReadingResponse:
    date_key = target_date.isoformat()

    cached = _cache_fresh(date_key)
    if cached:
        return cached

    lock = _readings_locks.setdefault(date_key, asyncio.Lock())
    async with lock:
        cached = _cache_fresh(date_key)
        if cached:
            return cached

        if time.monotonic() < _upstream_blocked_until:
            return _stale_or_unavailable(date_key)

        try:
            response = await _fetch_daily_reading_from_usccb(target_date)
        except HTTPException as exc:
            if exc.status_code >= 500:
                return _stale_or_unavailable(date_key, exc)
            raise

        _cache_store(date_key, response)
        return response


def _stale_or_unavailable(date_key: str, exc: Optional[HTTPException] = None) -> DailyReadingResponse:
    """Serve an expired cache entry if we have one (entries are only evicted by
    size, never deleted on expiry); otherwise surface a 503."""
    stale = _readings_cache.get(date_key)
    if stale:
        logger.warning(
            "Serving stale readings for %s (upstream unavailable: %s)",
            date_key,
            exc.detail if exc else "in cooldown",
        )
        return stale[1]
    if exc:
        raise exc
    raise HTTPException(
        status_code=503,
        detail="Upstream readings source is rate-limiting; please retry shortly",
    )


async def _fetch_daily_reading_from_usccb(target_date: date_cls) -> DailyReadingResponse:
    logger.info(f"Fetching mass readings for date: {target_date}")
    try:
        async with USCCB() as usccb:
            logger.info("USCCB context manager created successfully")
            mass = await usccb.get_mass_from_date(target_date)
            if mass is None:
                fallback_url = models.MassType.DEFAULT.to_url(target_date)
                logger.info(
                    "Primary mass lookup returned none; trying fallback URL %s",
                    fallback_url,
                )
                mass = await usccb.get_mass_from_url(fallback_url)
                if mass:
                    logger.info(f"Fallback URL worked: {mass.title}")
                else:
                    logger.error(f"Fallback URL also returned None for {fallback_url}")
            else:
                logger.info(f"Primary lookup worked: {mass.title}")
        if not mass:
            logger.error(f"No mass found for date {target_date}")
            raise HTTPException(status_code=404, detail="No mass readings found")
        logger.info("Converting mass to response format")
        return convert_mass_to_response(mass)
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except aiohttp.ClientResponseError as e:
        if e.status in (403, 429):
            global _upstream_blocked_until
            _upstream_blocked_until = time.monotonic() + UPSTREAM_COOLDOWN_SECONDS
            logger.warning(f"USCCB rate-limited request for {target_date}: {e.status}")
            raise HTTPException(
                status_code=503,
                detail="Upstream readings source is rate-limiting; please retry shortly",
            )
        if e.status == 404:
            raise HTTPException(status_code=404, detail="No mass readings found")
        logger.error(f"USCCB request failed for {target_date}: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Upstream error: {e.status}")
    except Exception as e:
        logger.error(f"Error fetching daily reading: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


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
    import traceback
    
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
        
        # Test URL generation
        test_date = datetime.now().date()
        url = test_models.MassType.DEFAULT.to_url(test_date)
        debug_info["url_generation"] = {"date": test_date.isoformat(), "url": url}
        
        # Test USCCB context manager creation
        try:
            usccb = TestUSCCB()
            debug_info["usccb_creation"] = "success"
        except Exception as e:
            debug_info["usccb_creation"] = f"failed: {str(e)}"
            debug_info["usccb_creation_traceback"] = traceback.format_exc()
            return debug_info
        
        # Test async context manager
        try:
            async with TestUSCCB() as usccb_context:
                debug_info["usccb_context"] = "success"
                
                # Try to get mass
                mass = await usccb_context.get_mass_from_date(test_date)
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
            debug_info["usccb_context"] = f"failed: {str(e)}"
            debug_info["usccb_context_traceback"] = traceback.format_exc()
            
    except Exception as e:
        debug_info["imports"] = f"failed: {str(e)}"
        debug_info["import_traceback"] = traceback.format_exc()
    
    return debug_info


@app.get("/test")
async def simple_test() -> Dict[str, Any]:
    """Simple test endpoint that doesn't use complex async operations."""
    try:
        from catholic_mass_readings import models
        test_date = datetime.now().date()
        url = models.MassType.DEFAULT.to_url(test_date)
        return {
            "status": "ok",
            "date": test_date.isoformat(),
            "generated_url": url,
            "expected_url": f"https://bible.usccb.org/bible/readings/{test_date.strftime('%m%d%y')}.cfm"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# Keep today's and tomorrow's readings warm so users never pay the upstream
# fetch (or eat a 503 when USCCB happens to be rate-limiting at that moment).
# Cache hits make the hourly pass free; failures are retried the next hour.
WARM_INTERVAL_SECONDS = 60 * 60


async def _warm_cache_loop() -> None:
    while True:
        for day_offset in (0, 1):
            target = USCCB.today() + timedelta(days=day_offset)
            try:
                await fetch_daily_reading(target)
            except HTTPException as exc:
                logger.warning("Cache warm for %s failed: %s", target, exc.detail)
            except Exception:
                logger.exception("Cache warm for %s failed unexpectedly", target)
        await asyncio.sleep(WARM_INTERVAL_SECONDS)


@app.on_event("startup")
async def _start_cache_warmer() -> None:
    asyncio.create_task(_warm_cache_loop())


@app.get("/readings", response_model=DailyReadingResponse)
async def get_readings(date: str = Query(..., description="Date in YYYY-MM-DD format")) -> DailyReadingResponse:
    target_date = _parse_date(date)
    return await fetch_daily_reading(target_date)


@app.get("/readings/today", response_model=DailyReadingResponse)
async def get_today_readings() -> DailyReadingResponse:
    return await fetch_daily_reading(USCCB.today())


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


class ProperText(BaseModel):
    kind: str  # entrance | communion | or | verse | other
    reference: str = ""
    text: str


class CelebrationPropers(BaseModel):
    celebration: str
    propers: List[ProperText]


class PropersResponse(BaseModel):
    date: str
    celebrations: List[CelebrationPropers]


# Mass propers (entrance/communion antiphons) are fixed per liturgical day,
# so they're served from a pre-harvested static dataset rather than scraped
# at runtime. Re-run scripts/harvest_antiphons.py to extend coverage.
PROPERS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "mass_propers.jsonl")


def _load_propers() -> Dict[str, Dict[str, Any]]:
    propers: Dict[str, Dict[str, Any]] = {}
    try:
        with open(PROPERS_PATH, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if row.get("celebrations"):
                    propers[row["date"]] = row
    except FileNotFoundError:
        logger.warning("Propers dataset not found at %s", PROPERS_PATH)
    logger.info("Loaded propers for %d days", len(propers))
    return propers


PROPERS_BY_DATE = _load_propers()


def _propers_for_date(target_date: date_cls) -> PropersResponse:
    row = PROPERS_BY_DATE.get(target_date.isoformat())
    if row is None:
        available = sorted(PROPERS_BY_DATE)
        coverage = f"{available[0]} to {available[-1]}" if available else "empty"
        raise HTTPException(
            status_code=404,
            detail=f"No propers for {target_date.isoformat()} (dataset covers {coverage})",
        )
    return PropersResponse(
        date=row["date"],
        celebrations=[
            CelebrationPropers(
                celebration=c["celebration"],
                propers=[ProperText(**p) for p in c["propers"]],
            )
            for c in row["celebrations"]
        ],
    )


@app.get("/propers/today", response_model=PropersResponse)
async def get_today_propers() -> PropersResponse:
    return _propers_for_date(USCCB.today())


@app.get("/propers/{date_str}", response_model=PropersResponse)
async def get_propers_by_date(date_str: str) -> PropersResponse:
    return _propers_for_date(_parse_date(date_str))


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
