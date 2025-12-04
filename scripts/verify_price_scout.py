
import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from bimcalc.intelligence.price_scout import SmartPriceScout

# Configure logging
logging.basicConfig(level=logging.INFO)

async def verify_scout():
    # Test URL (TLC Direct - a common UK electrical supplier)
    # This page contains a list of sockets
    url = "https://www.tlc-direct.co.uk/Main_Index/Wiring_Accessories_Menu_Index/A_White_All/BG_NEXUS/index.html"
    
    print(f"🔍 Testing Smart Price Scout on: {url}")
    
    try:
        async with SmartPriceScout() as scout:
            print("✅ SmartPriceScout initialized")
            
            print("🌐 Fetching and analyzing page...")
            result = await scout.extract(url)
            
            print("\n✨ Extraction Result:")
            import json
            print(json.dumps(result, indent=2))
            
            # Basic validation
            if result:
                print("\n✅ Extraction successful!")
            else:
                print("\n❌ Extraction returned empty result.")
                
    except Exception as e:
        print(f"\n❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_scout())
