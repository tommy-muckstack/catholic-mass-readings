#!/usr/bin/env python3

import asyncio
from datetime import date, datetime, timedelta
from catholic_mass_readings.usccb import USCCB
from catholic_mass_readings import models

async def test_recent_dates():
    """Test with recent and current dates."""
    dates_to_test = [
        date(2024, 9, 20),  # Past date 
        date(2024, 12, 1),  # Recent past
        date(2025, 1, 1),   # New Year 2025
        date(2025, 9, 25),  # Today's system date
    ]
    
    for test_date in dates_to_test:
        print(f"\n--- Testing date: {test_date} ---")
        
        try:
            async with USCCB() as usccb:
                mass = await usccb.get_mass_from_date(test_date)
                if mass:
                    print(f"✅ Found mass: {mass.title}")
                    print(f"URL: {mass.url}")
                else:
                    print(f"❌ No mass found for {test_date}")
                    
                    # Check what the max query date is
                    max_date = USCCB.max_query_date()
                    print(f"Max query date: {max_date}")
                    
        except Exception as e:
            print(f"❌ Error for {test_date}: {e}")

if __name__ == "__main__":
    asyncio.run(test_recent_dates())