#!/usr/bin/env python3
"""Debug script to help diagnose Railway deployment issues."""

import asyncio
import os
import sys
from datetime import date, datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def debug_environment():
    """Debug the current environment and dependencies."""
    print("=" * 60)
    print("ENVIRONMENT DEBUG")
    print("=" * 60)
    
    print(f"Python version: {sys.version}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    
    # Check environment variables
    railway_env = os.environ.get('RAILWAY_ENVIRONMENT', 'local')
    print(f"Railway environment: {railway_env}")
    
    # Check if packages can be imported
    print("\n--- Import Tests ---")
    try:
        from catholic_mass_readings.usccb import USCCB
        print("✅ Successfully imported USCCB from catholic_mass_readings.usccb")
    except ImportError as e:
        print(f"❌ Failed to import USCCB: {e}")
        return False
        
    try:
        from catholic_mass_readings import models
        print("✅ Successfully imported models from catholic_mass_readings")
    except ImportError as e:
        print(f"❌ Failed to import models: {e}")
        return False
    
    # Test USCCB functionality
    print("\n--- USCCB Tests ---")
    test_date = date(2025, 9, 25)
    url = models.MassType.DEFAULT.to_url(test_date)
    print(f"Generated URL for {test_date}: {url}")
    
    try:
        async with USCCB() as usccb:
            print("✅ USCCB context manager works")
            
            # Test direct URL access
            mass = await usccb.get_mass_from_url(url)
            if mass:
                print(f"✅ get_mass_from_url works: {mass.title}")
            else:
                print("❌ get_mass_from_url returned None")
                
            # Test date-based access
            mass2 = await usccb.get_mass_from_date(test_date)
            if mass2:
                print(f"✅ get_mass_from_date works: {mass2.title}")
            else:
                print("❌ get_mass_from_date returned None")
                
    except Exception as e:
        print(f"❌ USCCB test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test main.py imports and functions
    print("\n--- Main.py Tests ---")
    try:
        from main import fetch_daily_reading, app
        print("✅ Successfully imported from main.py")
        
        # Test the main function
        response = await fetch_daily_reading(test_date)
        print(f"✅ fetch_daily_reading works: {response.title}")
        print(f"   Reading date: {response.readingDate}")
        print(f"   Has first reading: {response.firstReading is not None}")
        print(f"   Has gospel: {response.gospel is not None}")
        
    except Exception as e:
        print(f"❌ Main.py test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n✅ All tests passed!")
    return True

if __name__ == "__main__":
    success = asyncio.run(debug_environment())
    sys.exit(0 if success else 1)