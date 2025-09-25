#!/usr/bin/env python3

import asyncio
from datetime import date
from usccb import USCCB

async def debug_verse_structure():
    """Debug the verse structure in parsed readings."""
    target_date = date(2025, 9, 25)
    
    try:
        async with USCCB() as usccb:
            mass = await usccb.get_mass_from_date(target_date)
            if mass:
                print(f"Mass title: {getattr(mass, 'title', 'No title')}")
                
                for i, section in enumerate(getattr(mass, 'sections', [])):
                    print(f"\nSection {i}:")
                    print(f"  Header: {getattr(section, 'header', 'No header')}")
                    print(f"  Type: {getattr(section, 'type_', 'No type')}")
                    
                    readings = getattr(section, 'readings', [])
                    print(f"  Readings count: {len(readings)}")
                    
                    for j, reading in enumerate(readings):
                        print(f"    Reading {j}:")
                        print(f"      Text: {getattr(reading, 'text', 'No text')[:100]}...")
                        print(f"      Header: {getattr(reading, 'header', 'No header')}")
                        
                        verses = getattr(reading, 'verses', [])
                        print(f"      Verses count: {len(verses)}")
                        print(f"      Verses type: {type(verses)}")
                        
                        for k, verse in enumerate(verses[:3]):  # Only show first 3 verses
                            print(f"        Verse {k}: {verse} (type: {type(verse)})")
                            if hasattr(verse, 'book'):
                                print(f"          Book: {verse.book}")
                            else:
                                print(f"          ERROR: No book attribute! Value: {verse}")
            else:
                print("No mass found")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_verse_structure())