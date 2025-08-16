"""
Test the USCCB parser logic with requests
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import date

def test_usccb_parsing():
    """Test parsing USCCB reading page"""
    
    # Test URL for August 16, 2025
    url = "https://bible.usccb.org/bible/readings/081625.cfm"
    
    print(f"Testing URL: {url}")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title
        title_tag = soup.find('title')
        title = title_tag.get_text().split('|')[0].strip() if title_tag else "Unknown"
        print(f"Title: {title}")
        
        # Extract lectionary number
        text = soup.get_text()
        lectionary_match = re.search(r'Lectionary:\s*(\d+)', text)
        lectionary = lectionary_match.group(1) if lectionary_match else None
        print(f"Lectionary: {lectionary}")
        
        # Find all paragraphs and analyze structure
        paragraphs = soup.find_all('p')
        
        print(f"\nFound {len(paragraphs)} paragraphs")
        
        readings = []
        current_reading = None
        
        for i, p in enumerate(paragraphs):
            text = p.get_text().strip()
            
            if not text:
                continue
                
            # Check for reading type indicators
            text_lower = text.lower()
            reading_type = None
            
            if 'reading' in text_lower and any(x in text_lower for x in ['1', 'first', ' i ']):
                reading_type = "first_reading"
            elif 'psalm' in text_lower or 'responsorial' in text_lower:
                reading_type = "responsorial_psalm"
            elif 'reading' in text_lower and any(x in text_lower for x in ['2', 'second', ' ii ']):
                reading_type = "second_reading"
            elif 'alleluia' in text_lower:
                reading_type = "alleluia"
            elif 'gospel' in text_lower:
                reading_type = "gospel"
            
            if reading_type:
                # Save previous reading
                if current_reading:
                    readings.append(current_reading)
                    print(f"✅ Saved {current_reading['type']}: {current_reading['title'][:50]}...")
                
                # Start new reading
                current_reading = {
                    "type": reading_type,
                    "title": text,
                    "content": "",
                    "reference": extract_scripture_reference(p)
                }
                print(f"🔍 Found {reading_type}: {text[:50]}...")
                
            elif current_reading and len(text) > 20:  # Only add substantial content
                # Add content to current reading
                if current_reading["content"]:
                    current_reading["content"] += "\n\n"
                current_reading["content"] += text
                print(f"📄 Added content to {current_reading['type']}: {text[:30]}...")
        
        # Add the last reading
        if current_reading:
            readings.append(current_reading)
            print(f"✅ Saved {current_reading['type']}: {current_reading['title'][:50]}...")
        
        print(f"\n📚 Total readings found: {len(readings)}")
        for reading in readings:
            print(f"  - {reading['type']}: {len(reading['content'])} chars")
            print(f"    Title: {reading['title']}")
            print(f"    Reference: {reading.get('reference', 'None')}")
            print(f"    Content preview: {reading['content'][:100]}...")
            print()
        
        return readings
        
    except Exception as e:
        print(f"Error: {e}")
        return None

def extract_scripture_reference(element):
    """Extract scripture reference from an element"""
    links = element.find_all('a', href=True)
    for link in links:
        href = link.get('href', '')
        if 'bible.usccb.org/bible/' in href:
            return link.get_text().strip()
    return None

if __name__ == "__main__":
    test_usccb_parsing()