#!/usr/bin/env python3
"""
Debug the USCCB scraper to see what's happening
"""

import requests
from bs4 import BeautifulSoup
import sys

def debug_scraper():
    """Debug the USCCB scraper step by step"""
    
    url = "https://bible.usccb.org/bible/readings/081625.cfm"
    print(f"🔍 Testing URL: {url}")
    
    try:
        # Test if URL is accessible
        response = requests.get(url)
        print(f"📡 HTTP Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ URL not accessible: {response.status_code}")
            return
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Test title extraction
        title_tag = soup.find('title')
        title = title_tag.get_text().split('|')[0].strip() if title_tag else "Unknown"
        print(f"📄 Page Title: {title}")
        
        # Test H3 headings (our new parsing method)
        headings = soup.find_all('h3')
        print(f"\n📋 Found {len(headings)} H3 headings:")
        
        for i, heading in enumerate(headings):
            header_text = heading.get_text(strip=True)
            print(f"  H3[{i}]: {header_text}")
            
            # Test finding content after each heading
            content_paragraphs = []
            current = heading.find_next_sibling()
            
            print(f"    Looking for content after H3[{i}]...")
            sibling_count = 0
            
            while current and current.name != 'h3' and sibling_count < 10:
                if current.name == 'p':
                    text = current.get_text(strip=True)
                    if text and not text.startswith('Lectionary'):
                        content_paragraphs.append(text[:100] + "..." if len(text) > 100 else text)
                        print(f"      Found paragraph: {text[:50]}...")
                current = current.find_next_sibling()
                sibling_count += 1
            
            if not content_paragraphs:
                # Try finding next paragraph in document order
                next_p = heading.find_next('p')
                if next_p:
                    text = next_p.get_text(strip=True)
                    if text and not text.startswith('Lectionary'):
                        content_paragraphs.append(text[:100] + "..." if len(text) > 100 else text)
                        print(f"      Found next paragraph: {text[:50]}...")
            
            print(f"    Content paragraphs found: {len(content_paragraphs)}")
            for j, para in enumerate(content_paragraphs[:3]):  # Show first 3
                print(f"      P[{j}]: {para}")
        
        # Test lectionary extraction
        text = soup.get_text()
        import re
        lectionary_match = re.search(r'Lectionary:\s*(\d+)', text)
        lectionary = lectionary_match.group(1) if lectionary_match else None
        print(f"\n📖 Lectionary: {lectionary}")
        
        # Summary
        print(f"\n📊 SUMMARY:")
        print(f"  - URL accessible: ✅")
        print(f"  - Title found: {'✅' if title != 'Unknown' else '❌'}")
        print(f"  - H3 headings: {len(headings)} {'✅' if len(headings) > 0 else '❌'}")
        print(f"  - Lectionary: {'✅' if lectionary else '❌'}")
        
        if len(headings) == 0:
            print("\n⚠️ No H3 headings found - this explains why the scraper isn't working!")
            print("Let's check what headings DO exist...")
            
            for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                elements = soup.find_all(tag)
                if elements:
                    print(f"  {tag.upper()}: {len(elements)} found")
                    for elem in elements[:3]:
                        print(f"    - {elem.get_text()[:50]}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_scraper()