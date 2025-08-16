#!/usr/bin/env python3
"""
Create a comprehensive debug endpoint to test in production
"""

import asyncio
import aiohttp
from datetime import date
from bs4 import BeautifulSoup

async def production_debug():
    """Debug what's happening in the production environment"""
    
    url = "https://bible.usccb.org/bible/readings/081625.cfm"
    
    async with aiohttp.ClientSession() as session:
        try:
            # Test basic URL access
            async with session.get(url) as response:
                print(f"📡 HTTP Status: {response.status}")
                
                if response.status != 200:
                    print(f"❌ URL not accessible: {response.status}")
                    return
                
                content = await response.text()
                print(f"📄 Content length: {len(content)} characters")
                
                # Parse HTML
                soup = BeautifulSoup(content, 'html.parser')
                
                # Test title extraction
                title_tag = soup.find('title')
                title = title_tag.get_text().split('|')[0].strip() if title_tag else "Unknown"
                print(f"📄 Page Title: {title}")
                
                # Test H3 headings
                headings = soup.find_all('h3')
                print(f"📋 Found {len(headings)} H3 headings:")
                
                for i, heading in enumerate(headings):
                    header_text = heading.get_text(strip=True)
                    print(f"  H3[{i}]: {header_text}")
                
                # Test if we can find any content
                all_text = soup.get_text()
                keywords = ['Joshua', 'Gospel', 'Reading', 'Psalm']
                for keyword in keywords:
                    if keyword.lower() in all_text.lower():
                        print(f"✅ Found keyword '{keyword}' in page content")
                    else:
                        print(f"❌ Keyword '{keyword}' NOT found in page content")
                
                return {
                    "status": response.status,
                    "content_length": len(content),
                    "title": title,
                    "h3_count": len(headings),
                    "h3_headers": [h.get_text(strip=True) for h in headings],
                    "has_mass_content": any(kw.lower() in all_text.lower() for kw in keywords)
                }
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

if __name__ == "__main__":
    result = asyncio.run(production_debug())
    print(f"\n📊 Final result: {result}")