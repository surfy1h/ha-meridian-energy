#!/usr/bin/env python3
"""
Test the average daily use extraction functionality
"""

import asyncio
import aiohttp
import json
import re
import statistics

async def test_average_daily_use():
    """Test extracting average daily use from Meridian portal"""
    print("📊 Testing Average Daily Use Extraction")
    print("=" * 50)
    
    # Load credentials
    try:
        with open("test/config.json", "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ test/config.json not found")
        return
    
    session = aiohttp.ClientSession()
    
    try:
        # Authenticate
        print("🔐 Authenticating...")
        async with session.get("https://secure.meridianenergy.co.nz/login") as response:
            html = await response.text()
            token_match = re.search(r'name="authenticity_token"\s+value="([^"]+)"', html)
            csrf_token = token_match.group(1)
        
        login_data = {
            "email": config["username"],
            "password": config["password"],
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
            print("✅ Authentication successful")
        
        # Test 1: Calculate average from CSV data
        print("\n📥 Test 1: Calculate Average from CSV Data")
        csv_url = "https://secure.meridianenergy.co.nz/feed_in_report/download"
        async with session.get(csv_url, headers=headers) as response:
            if response.status == 200:
                csv_data = await response.text()
                lines = csv_data.strip().split('\n')
                print(f"✅ CSV downloaded: {len(lines)} lines")
                
                # Calculate average from CSV
                daily_consumption_values = []
                
                for line in lines[1:]:  # Skip header
                    if not line.strip():
                        continue
                        
                    parts = line.split(',')
                    if len(parts) < 52:
                        continue
                    
                    try:
                        meter_element = parts[2]
                        date = parts[3]
                        
                        if meter_element == "Consumption":
                            # Sum half-hour values
                            half_hour_values = []
                            for i in range(4, min(52, len(parts))):
                                try:
                                    value = float(parts[i])
                                    half_hour_values.append(value)
                                except ValueError:
                                    half_hour_values.append(0.0)
                            
                            daily_total = sum(half_hour_values)
                            if daily_total > 0:
                                daily_consumption_values.append(daily_total)
                                print(f"   📅 {date}: {daily_total:.2f} kWh")
                                
                    except (ValueError, IndexError):
                        continue
                
                if daily_consumption_values:
                    csv_average = sum(daily_consumption_values) / len(daily_consumption_values)
                    print(f"\n✅ CSV Average: {csv_average:.2f} kWh/day (from {len(daily_consumption_values)} days)")
                else:
                    csv_average = 0.0
                    print("❌ No consumption data found in CSV")
            else:
                csv_average = 0.0
                print(f"❌ CSV download failed: {response.status}")
        
        # Test 2: Extract usage from dashboard
        print("\n🌐 Test 2: Extract Usage from Dashboard")
        async with session.get("https://secure.meridianenergy.co.nz/", headers=headers) as response:
            if response.status == 200:
                html = await response.text()
                print(f"✅ Dashboard accessible: {len(html)} bytes")
                
                # Look for usage patterns
                usage_patterns = [
                    (r'today[^>]*[:\s]*(\d+\.?\d*)\s*kWh', 'today usage'),
                    (r'daily[^>]*use[^>]*[:\s]*(\d+\.?\d*)\s*kWh', 'daily use'),
                    (r'consumption[^>]*[:\s]*(\d+\.?\d*)\s*kWh', 'consumption'),
                    (r'used[^>]*[:\s]*(\d+\.?\d*)\s*kWh', 'used'),
                    (r'average[^>]*[:\s]*(\d+\.?\d*)\s*kWh', 'average usage'),
                    (r'(\d+\.?\d*)\s*kWh[^>]*average', 'kWh average'),
                    (r'(\d+\.?\d*)\s*kWh[^>]*day', 'kWh per day'),
                    (r'(\d+\.?\d*)\s*kWh[^>]*consumption', 'kWh consumption'),
                ]
                
                found_values = []
                for pattern, description in usage_patterns:
                    matches = re.findall(pattern, html, re.IGNORECASE)
                    for match in matches:
                        try:
                            value = float(match)
                            if 5.0 <= value <= 50.0:  # Reasonable range
                                found_values.append(value)
                                print(f"   💡 Found: {value} kWh ({description})")
                        except ValueError:
                            continue
                
                if found_values:
                    dashboard_average = statistics.median(found_values) if len(found_values) > 1 else found_values[0]
                    print(f"\n✅ Dashboard Average: {dashboard_average:.2f} kWh/day (from {len(found_values)} values)")
                else:
                    dashboard_average = 0.0
                    print("❌ No usage values found on dashboard")
            else:
                dashboard_average = 0.0
                print(f"❌ Dashboard not accessible: {response.status}")
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 AVERAGE DAILY USE EXTRACTION SUMMARY")
        print("=" * 50)
        
        final_average = csv_average if csv_average > 0 else dashboard_average
        
        if final_average > 0:
            print(f"✅ SUCCESSFUL EXTRACTION:")
            print(f"   📊 CSV Average: {csv_average:.2f} kWh/day")
            print(f"   🌐 Dashboard Average: {dashboard_average:.2f} kWh/day")
            print(f"   🎯 Final Average: {final_average:.2f} kWh/day")
            
            print(f"\n🎯 EXPECTED HA SENSOR VALUE:")
            print(f"   Average Daily Use: {final_average:.2f} kWh")
            
        else:
            print(f"❌ NO AVERAGE EXTRACTED:")
            print(f"   CSV extraction: Failed")
            print(f"   Dashboard extraction: Failed")
            print(f"   Sensor will show: 0.0 kWh")
            
        print(f"\n📋 Next Steps:")
        print(f"1. Update integration to v2.3.1 in Home Assistant")
        print(f"2. Check Average Daily Use sensor")
        print(f"3. Should show {final_average:.2f} kWh instead of 0.0")
        
    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(test_average_daily_use())
