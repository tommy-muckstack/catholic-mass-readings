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
import sys

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
        "source": "USCCB via catholic-mass-readings library",
        "version": "1.1.0-debug"
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
            if not mass:
                raise HTTPException(status_code=404, detail="No mass readings found")
            return convert_mass_to_response(mass)
    except HTTPException:
        raise
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
            if not mass:
                raise HTTPException(status_code=404, detail="No mass readings found")
            return convert_mass_to_response(mass)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching readings for {date_str}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch readings: {str(e)}")

@app.get("/readings/{date_str}/alternates")
async def get_alternate_readings(date_str: str):
    """Get alternate readings for a specific date (saints, memorials, etc.)"""
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        async with USCCB() as usccb:
            alternate_masses = await usccb.get_alternate_readings(target_date)
            
            results = []
            for mass in alternate_masses:
                results.append(convert_mass_to_response(mass))
            
            return {
                "date": date_str,
                "alternate_readings": results,
                "count": len(results)
            }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error fetching alternate readings for {date_str}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch alternate readings: {str(e)}")

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

@app.get("/debug")
async def debug_production():
    """Debug endpoint to understand production environment issues"""
    import aiohttp
    from bs4 import BeautifulSoup
    from datetime import date
    
    url = "https://bible.usccb.org/bible/readings/081625.cfm"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                status = response.status
                content = await response.text()
                content_length = len(content)
                
                # Parse HTML
                soup = BeautifulSoup(content, 'html.parser')
                
                # Test title extraction
                title_tag = soup.find('title')
                title = title_tag.get_text().split('|')[0].strip() if title_tag else "Unknown"
                
                # Test H3 headings
                headings = soup.find_all('h3')
                h3_headers = [h.get_text(strip=True) for h in headings]
                
                # Test if we can find mass content keywords
                all_text = soup.get_text()
                keywords = ['Joshua', 'Gospel', 'Reading', 'Psalm']
                keyword_results = {}
                for keyword in keywords:
                    keyword_results[keyword] = keyword.lower() in all_text.lower()
                
                # Also test the USCCB library
                library_result = {}
                try:
                    async with USCCB() as usccb:
                        mass = await usccb.get_today_mass()
                        library_result = {
                            "mass_found": mass is not None,
                            "mass_title": getattr(mass, 'title', None) if mass else None,
                            "sections_count": len(mass.sections) if mass and hasattr(mass, 'sections') else 0,
                            "mass_url": getattr(mass, 'url', None) if mass else None
                        }
                except Exception as lib_error:
                    library_result = {
                        "error": str(lib_error),
                        "mass_found": False
                    }
                
                return {
                    "url_test": {
                        "url": url,
                        "status": status,
                        "content_length": content_length,
                        "title": title,
                        "h3_count": len(headings),
                        "h3_headers": h3_headers,
                        "keyword_results": keyword_results,
                        "has_mass_content": any(keyword_results.values())
                    },
                    "library_test": library_result,
                    "environment": {
                        "railway_env": os.environ.get('RAILWAY_ENVIRONMENT', 'not_set'),
                        "port": os.environ.get('PORT', 'not_set'),
                        "python_version": sys.version
                    }
                }
                
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "url": url
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