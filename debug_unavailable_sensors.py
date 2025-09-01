#!/usr/bin/env python3
"""
Debug script to identify why sensors are showing "Unavailable"
This simulates exactly what the HA coordinator does
"""

import asyncio
import aiohttp
import json
import re
from datetime import datetime, timedelta
import logging

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
)

async def debug_coordinator_issues():
    """Debug the exact coordinator process that HA uses"""
    print("🔍 Debugging Unavailable Sensors - HA Coordinator Simulation")
    print("=" * 70)
    
    # Load credentials
    try:
        with open("test/config.json", "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ test/config.json not found")
        return
    
    username = config["username"]
    password = config["password"]
    
    # Create session with same settings as coordinator
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=2)
    timeout = aiohttp.ClientTimeout(total=30, connect=10)
    session = aiohttp.ClientSession(
        connector=connector,
        timeout=timeout,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
    )
    
    try:
        print(f"\n🔐 Step 1: Authentication Test")
        print(f"   Username: {username}")
        print(f"   Password: {'*' * len(password)}")
        
        # Step 1: Get login page
        print("\n   📄 Getting login page...")
        async with session.get("https://secure.meridianenergy.co.nz/login") as response:
            if response.status != 200:
                print(f"   ❌ Login page failed: {response.status}")
                return
            
            html = await response.text()
            print(f"   ✅ Login page loaded ({len(html)} chars)")
            
            # Extract CSRF token
            token_match = re.search(r'name="authenticity_token"\s+value="([^"]+)"', html)
            if not token_match:
                print("   ❌ CSRF token not found")
                return
                
            csrf_token = token_match.group(1)
            print(f"   ✅ CSRF token: {csrf_token[:20]}...")
        
        # Step 2: Login
        print("\n   🔑 Attempting login...")
        login_data = {
            "email": username,
            "password": password,
            "authenticity_token": csrf_token,
            "commit": "Sign in"
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://secure.meridianenergy.co.nz/login",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        async with session.post("https://secure.meridianenergy.co.nz/", 
                               data=login_data, headers=headers, allow_redirects=False) as response:
            
            print(f"   Login response: {response.status}")
            if response.status not in [200, 302, 303]:
                print(f"   ❌ Login failed with status {response.status}")
                response_text = await response.text()
                print(f"   Response preview: {response_text[:200]}...")
                return
            
            print("   ✅ Login successful!")
        
        # Step 3: Test dashboard access
        print(f"\n📊 Step 2: Dashboard Access Test")
        async with session.get("https://secure.meridianenergy.co.nz/", headers=headers) as response:
            if response.status != 200:
                print(f"   ❌ Dashboard access failed: {response.status}")
                return
            
            dashboard_html = await response.text()
            print(f"   ✅ Dashboard accessible ({len(dashboard_html)} chars)")
            
            # Check for logged-in indicators
            if "sign out" in dashboard_html.lower() or "logout" in dashboard_html.lower():
                print("   ✅ Confirmed logged in (found sign out link)")
            else:
                print("   ⚠️ May not be logged in (no sign out link found)")
        
        # Step 4: Test CSV download (primary data source)
        print(f"\n📥 Step 3: CSV Download Test")
        csv_urls = [
            "https://secure.meridianenergy.co.nz/feed_in_report.csv",
            "https://secure.meridianenergy.co.nz/feed_in_report/download",
            "https://secure.meridianenergy.co.nz/feed_in_report/export",
            "https://secure.meridianenergy.co.nz/customers/feed_in_report.csv"
        ]
        
        csv_success = False
        for csv_url in csv_urls:
            print(f"   Trying: {csv_url}")
            async with session.get(csv_url, headers=headers) as response:
                print(f"   Status: {response.status}")
                
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    csv_data = await response.text()
                    
                    print(f"   Content-Type: {content_type}")
                    print(f"   Data size: {len(csv_data)} bytes")
                    
                    if len(csv_data) > 100 and (',' in csv_data or 'csv' in content_type.lower()):
                        print("   ✅ Valid CSV data found!")
                        csv_success = True
                        
                        # Parse for today's data
                        lines = csv_data.strip().split('\n')
                        print(f"   CSV has {len(lines)} lines")
                        
                        today = datetime.now().strftime("%-d/%-m/%Y")
                        print(f"   Looking for today's data: {today}")
                        
                        found_today = False
                        for line in lines[1:5]:  # Check first few data lines
                            if today in line:
                                found_today = True
                                print(f"   ✅ Found today's data: {line[:80]}...")
                                break
                        
                        if not found_today:
                            print(f"   ⚠️ No data for today ({today})")
                            print("   Sample dates in CSV:")
                            for line in lines[1:4]:
                                if line.strip():
                                    parts = line.split(',')
                                    if len(parts) > 3:
                                        print(f"      {parts[3]}")
                        break
                    else:
                        print(f"   ❌ Invalid CSV data")
                else:
                    print(f"   ❌ Failed: {response.status}")
        
        if not csv_success:
            print("   ❌ No CSV data available - this is likely the main issue!")
        
        # Step 5: Test page scraping fallback
        print(f"\n🕷️ Step 4: Page Scraping Fallback Test")
        pages = [
            ("https://secure.meridianenergy.co.nz/usage", "usage"),
            ("https://secure.meridianenergy.co.nz/feed_in_report", "feed_in")
        ]
        
        for url, page_type in pages:
            print(f"   Testing {page_type} page...")
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    print(f"   ✅ {page_type} page accessible ({len(html)} chars)")
                    
                    # Look for energy data
                    kwh_matches = re.findall(r'(\d+\.?\d*)\s*kWh', html, re.IGNORECASE)
                    if kwh_matches:
                        print(f"   ✅ Found kWh values: {kwh_matches[:3]}")
                    else:
                        print(f"   ⚠️ No kWh values found")
                else:
                    print(f"   ❌ {page_type} page failed: {response.status}")
        
        # Summary and recommendations
        print(f"\n" + "=" * 70)
        print(f"🎯 DIAGNOSIS SUMMARY")
        print(f"=" * 70)
        
        if csv_success:
            print("✅ CSV Download: Working")
            print("✅ Authentication: Working")
            print("✅ Data Source: Available")
            print("\n💡 LIKELY ISSUE: Data parsing or coordinator error")
            print("   - Check Home Assistant logs for coordinator errors")
            print("   - Verify integration is using correct date format")
            print("   - Check if integration is looking for wrong date")
        else:
            print("❌ CSV Download: Failed")
            print("❌ Primary Data Source: Unavailable")
            print("\n💡 LIKELY ISSUE: Authentication or portal access")
            print("   - Credentials may be incorrect")
            print("   - Account may be locked or require verification")
            print("   - Portal structure may have changed")
        
        print(f"\n🔧 NEXT STEPS:")
        print("1. Check Home Assistant logs for specific error messages")
        print("2. Add debug logging to configuration.yaml")
        print("3. Try manually triggering sensor update in HA")
        print("4. Verify credentials are correct in HA integration config")
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(debug_coordinator_issues())
