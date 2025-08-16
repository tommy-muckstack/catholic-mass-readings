"""
Updated USCCB parser that works with the current HTML structure (2025)
"""

import re
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import Optional, List, Dict, Any
import logging
from datetime import date

logger = logging.getLogger(__name__)

class USCCBParser:
    """Updated parser for USCCB readings that works with current HTML structure"""
    
    def __init__(self):
        self.base_url = "https://bible.usccb.org/bible/readings"
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def get_daily_reading_url(self, reading_date: date) -> str:
        """Generate URL for daily readings"""
        return f"{self.base_url}/{reading_date.strftime('%m%d%y')}.cfm"
    
    def get_memorial_reading_urls(self, reading_date: date) -> List[str]:
        """Generate potential URLs for memorial/saint day readings"""
        base_date = reading_date.strftime('%m%d')
        
        # Common patterns for memorial readings
        patterns = [
            f"{base_date}-memorial-",
            f"{base_date}-feast-", 
            f"{base_date}-saint-",
            f"{base_date}-optional-"
        ]
        
        return patterns
    
    async def get_readings_for_date(self, reading_date: date) -> Dict[str, Any]:
        """Get all available readings for a specific date"""
        results = {
            "date": reading_date.isoformat(),
            "daily_reading": None,
            "alternate_readings": []
        }
        
        # Get main daily reading
        daily_url = self.get_daily_reading_url(reading_date)
        daily_reading = await self.scrape_reading_page(daily_url)
        if daily_reading:
            results["daily_reading"] = daily_reading
        
        # Try to find alternate readings
        memorial_patterns = self.get_memorial_reading_urls(reading_date)
        for pattern in memorial_patterns:
            # This would need additional logic to discover actual memorial URLs
            # For now, we'll implement the parser structure
            pass
        
        return results
    
    async def scrape_reading_page(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape a USCCB reading page and extract structured data"""
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"Failed to fetch {url}: {response.status}")
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                return self.parse_reading_content(soup, url)
                
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None
    
    def parse_reading_content(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Parse the reading content from BeautifulSoup object"""
        
        # Extract page title
        title_tag = soup.find('title')
        title = title_tag.get_text().split('|')[0].strip() if title_tag else "Unknown"
        
        # Extract lectionary number
        lectionary = self.extract_lectionary_number(soup)
        
        # Parse all reading sections
        readings = self.extract_readings(soup)
        
        return {
            "url": url,
            "title": title,
            "lectionary": lectionary,
            "readings": readings
        }
    
    def extract_lectionary_number(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract lectionary number from the page"""
        # Look for "Lectionary: XXX" pattern
        text = soup.get_text()
        match = re.search(r'Lectionary:\s*(\d+)', text)
        return match.group(1) if match else None
    
    def extract_readings(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract all reading sections from the page"""
        readings = []
        
        # The current USCCB structure uses a more simple approach
        # We need to identify reading sections by their patterns
        
        # Find all text content and parse it sequentially
        content = soup.get_text()
        
        # Split content into sections based on reading patterns
        sections = self.split_into_reading_sections(content, soup)
        
        for section in sections:
            if section:
                readings.append(section)
        
        return readings
    
    def split_into_reading_sections(self, content: str, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Split content into distinct reading sections"""
        readings = []
        
        # Look for reading patterns in the HTML
        # Current USCCB pages have readings in sequential order
        
        # Method 1: Look for paragraph tags with reading content
        paragraphs = soup.find_all('p')
        
        current_reading = None
        reading_type = None
        
        for p in paragraphs:
            text = p.get_text().strip()
            
            # Skip empty paragraphs
            if not text:
                continue
            
            # Check if this paragraph starts a new reading section
            new_type = self.identify_reading_type(text)
            if new_type:
                # Save previous reading if exists
                if current_reading:
                    readings.append(current_reading)
                
                # Start new reading
                reading_type = new_type
                current_reading = {
                    "type": reading_type,
                    "title": text,
                    "content": "",
                    "reference": self.extract_scripture_reference(p)
                }
            elif current_reading and text:
                # Add content to current reading
                if current_reading["content"]:
                    current_reading["content"] += "\n\n"
                current_reading["content"] += text
        
        # Add the last reading
        if current_reading:
            readings.append(current_reading)
        
        return readings
    
    def identify_reading_type(self, text: str) -> Optional[str]:
        """Identify the type of reading from text"""
        text_lower = text.lower()
        
        if 'reading' in text_lower and ('1' in text or 'i' in text_lower or 'first' in text_lower):
            return "first_reading"
        elif 'psalm' in text_lower or 'responsorial' in text_lower:
            return "responsorial_psalm"
        elif 'reading' in text_lower and ('2' in text or 'ii' in text_lower or 'second' in text_lower):
            return "second_reading"
        elif 'alleluia' in text_lower:
            return "alleluia"
        elif 'gospel' in text_lower:
            return "gospel"
        
        return None
    
    def extract_scripture_reference(self, element) -> Optional[str]:
        """Extract scripture reference from an element"""
        # Look for links to bible passages
        links = element.find_all('a', href=True)
        for link in links:
            href = link.get('href', '')
            if 'bible.usccb.org/bible/' in href:
                return link.get_text().strip()
        return None

# Integration with existing models
def convert_to_daily_reading_response(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert parsed USCCB data to the API response format"""
    
    if not parsed_data:
        return None
    
    readings = parsed_data.get("readings", [])
    
    # Map readings by type
    reading_map = {}
    for reading in readings:
        reading_map[reading["type"]] = {
            "type": reading["type"],
            "title": reading.get("title", ""),
            "reference": reading.get("reference", ""),
            "content": reading.get("content", ""),
            "verses": []
        }
    
    return {
        "id": f"usccb-updated-{parsed_data.get('url', '').split('/')[-1].replace('.cfm', '')}",
        "title": parsed_data.get("title", "Mass Readings"),
        "description": f"Mass readings from USCCB - Lectionary {parsed_data.get('lectionary', 'Unknown')}",
        "readingDate": "",  # Will be set by caller
        "audioUrl": None,
        "duration": None,
        "author": "USCCB",
        "subtitle": parsed_data.get("title", ""),
        "firstReading": reading_map.get("first_reading"),
        "responsorialPsalm": reading_map.get("responsorial_psalm"), 
        "secondReading": reading_map.get("second_reading"),
        "gospel": reading_map.get("gospel"),
        "hasTextContent": len(reading_map) > 0,
        "hasAudio": False
    }

# Test function
async def test_parser():
    """Test the updated parser"""
    test_date = date(2025, 8, 16)
    
    async with USCCBParser() as parser:
        readings = await parser.get_readings_for_date(test_date)
        print("Parsed readings:", readings)
        
        if readings["daily_reading"]:
            api_response = convert_to_daily_reading_response(readings["daily_reading"])
            print("API Response:", api_response)

if __name__ == "__main__":
    asyncio.run(test_parser())