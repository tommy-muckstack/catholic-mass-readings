#!/usr/bin/env python3

import asyncio
import sys
from datetime import date, datetime
from catholic_mass_readings.usccb import USCCB
from catholic_mass_readings import models

async def test_scraper():
    """Test the USCCB scraper directly."""
    print("Testing USCCB scraper...")
    
    # Test with a recent date that should exist
    test_date = date(2024, 12, 25)  # Christmas 2024
    print(f"Testing with date: {test_date}")
    
    try:
        async with USCCB() as usccb:
            print("Getting mass for test date...")
            mass = await usccb.get_mass_from_date(test_date)
            if mass:
                print(f"✅ Got mass: {mass.title}")
                print(f"Date: {mass.date}")
                print(f"URL: {mass.url}")
                print(f"Sections: {len(mass.sections)}")
                
                for i, section in enumerate(mass.sections):
                    print(f"  Section {i}: {section.header}")
                    print(f"    Type: {section.type_}")
                    print(f"    Readings: {len(section.readings)}")
            else:
                print("❌ No mass found")
                
                # Try different mass types
                print("Trying different mass types...")
                for mass_type in models.MassType:
                    try:
                        url = mass_type.to_url(test_date)
                        print(f"  Testing {mass_type}: {url}")
                        mass = await usccb.get_mass(test_date, mass_type)
                        if mass:
                            print(f"  ✅ Found mass with {mass_type}: {mass.title}")
                            return mass
                    except Exception as e:
                        print(f"  ❌ {mass_type} failed: {e}")
                
    except Exception as e:
        print(f"Error testing USCCB: {e}")
        import traceback
        traceback.print_exc()

async def test_url_directly():
    """Test accessing USCCB URL directly."""
    test_date = date(2024, 12, 25)
    url = models.MassType.DEFAULT.to_url(test_date)
    print(f"\nTesting URL directly: {url}")
    
    try:
        async with USCCB() as usccb:
            mass = await usccb.get_mass_from_url(url)
            if mass:
                print(f"✅ Got mass from URL: {mass.title}")
            else:
                print("❌ No mass found from URL")
    except Exception as e:
        print(f"❌ Error accessing URL: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_scraper())
    asyncio.run(test_url_directly())