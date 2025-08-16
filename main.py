#!/usr/bin/env python3
"""
Simple FastAPI wrapper for catholic-mass-readings library - Railway deployment
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import logging
import os

# Import the catholic-mass-readings library (local copy)
from usccb import USCCB

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Catholic Mass Readings API",
    description="REST API wrapper for catholic-mass-readings library",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Response models
class ReadingText(BaseModel):
    type: str
    title: str
    reference: str
    content: str
    verses: Optional[List[Dict]] = []

class DailyReadingResponse(BaseModel):
    id: str
    title: str
    description: str
    readingDate: str
    audioUrl: Optional[str] = None
    duration: Optional[str] = None
    author: str = "USCCB"
    subtitle: Optional[str] = None
    firstReading: Optional[ReadingText] = None
    responsorialPsalm: Optional[ReadingText] = None
    secondReading: Optional[ReadingText] = None
    gospel: Optional[ReadingText] = None
    hasTextContent: bool = True
    hasAudio: bool = False

def extract_reading_content(section) -> Optional[ReadingText]:
    """Extract readable content from a mass section"""
    if not section or not hasattr(section, 'readings') or not section.readings:
        return None
    
    # Combine all readings in the section
    combined_text = ""
    for reading in section.readings:
        if hasattr(reading, 'text') and reading.text:
            combined_text += reading.text.strip() + "\n\n"
    
    if not combined_text.strip():
        return None
    
    section_type = str(getattr(section, 'type_', 'Reading'))
    header = getattr(section, 'header', section_type)
    
    return ReadingText(
        type=section_type,
        title=header,
        reference=header,
        content=combined_text.strip(),
        verses=[]
    )

def convert_mass_to_response(mass) -> DailyReadingResponse:
    """Convert Mass object to API response"""
    if not mass:
        raise HTTPException(status_code=404, detail="No mass readings found")
    
    # Extract sections
    first_reading = None
    psalm = None
    second_reading = None
    gospel = None
    
    for section in mass.sections:
        section_type = str(getattr(section, 'type_', '')).lower()
        
        if 'first' in section_type or ('reading' in section_type and not first_reading):
            first_reading = extract_reading_content(section)
        elif 'psalm' in section_type:
            psalm = extract_reading_content(section)
        elif 'second' in section_type:
            second_reading = extract_reading_content(section)
        elif 'gospel' in section_type:
            gospel = extract_reading_content(section)
    
    # Generate response
    mass_date = getattr(mass, 'date', date.today())
    date_str = str(mass_date)
    
    return DailyReadingResponse(
        id=f"usccb-{date_str}",
        title=f"Mass Readings for {mass_date.strftime('%A, %B %d, %Y') if hasattr(mass_date, 'strftime') else date_str}",
        description=getattr(mass, 'title', "Daily Mass readings from USCCB"),
        readingDate=date_str,
        subtitle=getattr(mass, 'title', None),
        firstReading=first_reading,
        responsorialPsalm=psalm,
        secondReading=second_reading,
        gospel=gospel,
        hasTextContent=bool(first_reading or psalm or gospel)
    )

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Catholic Mass Readings API",
        "status": "active",
        "source": "USCCB via catholic-mass-readings library"
    }

@app.get("/health")
async def health_check():
    """Health check for Railway"""
    return {"status": "healthy", "service": "catholic-mass-readings-api"}

@app.get("/readings/today", response_model=DailyReadingResponse)
async def get_today_readings():
    """Get today's mass readings"""
    try:
        async with USCCB() as usccb:
            mass = await usccb.get_today_mass()
            return convert_mass_to_response(mass)
    except Exception as e:
        logger.error(f"Error fetching today's readings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch readings: {str(e)}")

@app.get("/readings/{date_str}", response_model=DailyReadingResponse)
async def get_readings_by_date(date_str: str):
    """Get mass readings for a specific date (YYYY-MM-DD)"""
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        async with USCCB() as usccb:
            mass = await usccb.get_mass_from_date(target_date)
            return convert_mass_to_response(mass)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error fetching readings for {date_str}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch readings: {str(e)}")

@app.get("/test")
async def test_library():
    """Test if the library is working"""
    try:
        async with USCCB() as usccb:
            mass = await usccb.get_today_mass()
            return {
                "library_working": True,
                "mass_found": mass is not None,
                "mass_title": getattr(mass, 'title', None) if mass else None,
                "sections_count": len(mass.sections) if mass and hasattr(mass, 'sections') else 0
            }
    except Exception as e:
        return {
            "library_working": False,
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    import sys
    
    # Get port from environment with Railway-friendly defaults
    port = int(os.environ.get("PORT", 8000))
    
    print(f"Starting server on 0.0.0.0:{port}")
    print(f"Python version: {sys.version}")
    print(f"Environment: {os.environ.get('RAILWAY_ENVIRONMENT', 'development')}")
    
    try:
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=port,
            log_level="info",
            access_log=True
        )
    except Exception as e:
        print(f"Failed to start server: {e}")
        sys.exit(1)