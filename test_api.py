#!/usr/bin/env python3

import asyncio
import sys
from datetime import date, datetime
from catholic_mass_readings import models
from usccb import USCCB

async def test_usccb():
    """Test the USCCB scraper directly."""
    print("Testing USCCB scraper...")
    
    try:
        async with USCCB() as usccb:
            print("Getting today's mass...")
            mass = await usccb.get_today_mass()
            if mass:
                print(f"Got mass: {mass}")
                print(f"Title: {getattr(mass, 'title', 'No title')}")
                print(f"Date: {getattr(mass, 'date', 'No date')}")
                print(f"URL: {getattr(mass, 'url', 'No URL')}")
                print(f"Sections: {len(getattr(mass, 'sections', []))}")
                
                for i, section in enumerate(getattr(mass, 'sections', [])):
                    print(f"  Section {i}: {getattr(section, 'header', 'No header')}")
                    print(f"    Type: {getattr(section, 'type_', 'No type')}")
                    print(f"    Readings: {len(getattr(section, 'readings', []))}")
            else:
                print("No mass found")
                
    except Exception as e:
        print(f"Error testing USCCB: {e}")
        import traceback
        traceback.print_exc()

async def test_specific_date():
    """Test with a specific date."""
    target_date = date(2025, 9, 25)
    print(f"\nTesting specific date: {target_date}")
    
    try:
        async with USCCB() as usccb:
            mass = await usccb.get_mass_from_date(target_date)
            if mass:
                print(f"Got mass for {target_date}: {getattr(mass, 'title', 'No title')}")
            else:
                print(f"No mass found for {target_date}")
                # Try fallback
                fallback_url = models.MassType.DEFAULT.to_url(target_date)
                print(f"Trying fallback URL: {fallback_url}")
                mass = await usccb.get_mass_from_url(fallback_url)
                if mass:
                    print(f"Got mass from fallback: {getattr(mass, 'title', 'No title')}")
                else:
                    print("No mass found from fallback either")
                    
    except Exception as e:
        print(f"Error testing specific date: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_usccb())
    asyncio.run(test_specific_date())