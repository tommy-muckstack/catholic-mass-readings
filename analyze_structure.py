"""
Analyze the actual HTML structure of USCCB pages
"""

import requests
from bs4 import BeautifulSoup

def analyze_page_structure():
    """Analyze the HTML structure of the USCCB page"""
    
    url = "https://bible.usccb.org/bible/readings/081625.cfm"
    
    response = requests.get(url)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    print("=== ANALYZING HTML STRUCTURE ===\n")
    
    # Look for all headings
    print("📄 HEADINGS FOUND:")
    for i in range(1, 7):
        headings = soup.find_all(f'h{i}')
        if headings:
            print(f"H{i} tags: {len(headings)}")
            for h in headings[:3]:  # Show first 3
                print(f"  - {h.get_text().strip()}")
    
    print("\n📄 DIVS WITH CLASSES:")
    divs = soup.find_all('div', class_=True)
    classes = set()
    for div in divs:
        for cls in div.get('class', []):
            classes.add(cls)
    
    for cls in sorted(classes)[:10]:  # Show first 10 classes
        count = len(soup.find_all('div', class_=cls))
        print(f"  .{cls}: {count} elements")
    
    print("\n📄 LOOKING FOR READING PATTERNS:")
    
    # Look for text patterns that indicate readings
    text = soup.get_text()
    
    # Common reading indicators
    patterns = [
        r'Reading\s+\d+',
        r'First\s+Reading',
        r'Second\s+Reading', 
        r'Responsorial\s+Psalm',
        r'Gospel',
        r'Alleluia',
        r'A reading from'
    ]
    
    import re
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            print(f"  '{pattern}': {len(matches)} matches - {matches}")
    
    print("\n📄 PARAGRAPH ANALYSIS:")
    paragraphs = soup.find_all('p')
    print(f"Total paragraphs: {len(paragraphs)}")
    
    for i, p in enumerate(paragraphs[:10]):  # First 10 paragraphs
        text = p.get_text().strip()
        if text:
            print(f"P{i}: {text[:100]}...")
            # Check for links
            links = p.find_all('a')
            if links:
                print(f"     Links: {[a.get_text()[:30] for a in links]}")
    
    print("\n📄 LOOKING FOR STRUCTURED CONTENT:")
    
    # Look for common structural elements
    for tag in ['article', 'section', 'main', 'content']:
        elements = soup.find_all(tag)
        if elements:
            print(f"{tag.upper()} elements: {len(elements)}")
    
    # Look for elements with specific IDs
    elements_with_ids = soup.find_all(attrs={'id': True})
    if elements_with_ids:
        print(f"\nElements with IDs:")
        for elem in elements_with_ids[:5]:
            print(f"  #{elem.get('id')}: {elem.name}")

if __name__ == "__main__":
    analyze_page_structure()