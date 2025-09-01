#!/usr/bin/env python3
"""
Simple test to verify data extraction works for HA sensors
Tests the core coordinator functionality without HA dependencies
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
import sys
import os

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
)

async def test_sensor_data_extraction():
    """Test data extraction as the HA coordinator would do it"""
    print("🚀 Testing Meridian Solar Data Extraction for HA Sensors")
    print("=" * 60)
    
    # Load credentials
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ config.json not found")
        return
    
    username = config["username"]
    password = config["password"]
    
    # Test the data extraction that HA would use
    session = aiohttp.ClientSession()
    
    try:
        print("\n🔐 Testing Authentication...")
        
        # Get login page
        async with session.get("https://secure.meridianenergy.co.nz/login") as response:
            if response.status != 200:
                print(f"❌ Can't access login page: {response.status}")
                return
            
            html = await response.text()
            import re
            token_match = re.search(r'name="authenticity_token"\s+value="([^"]+)"', html)
            if not token_match:
                print("❌ Can't find CSRF token")
                return
            
            csrf_token = token_match.group(1)
            print("✅ Got CSRF token")
        
        # Login
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
            
            if response.status not in [200, 302, 303]:
                print(f"❌ Login failed: {response.status}")
                return
            
            print("✅ Login successful!")
        
        print("\n📥 Testing CSV Data Download...")
        
        # Test CSV download (primary data source)
        csv_url = "https://secure.meridianenergy.co.nz/feed_in_report/download"
        async with session.get(csv_url, headers=headers) as response:
            if response.status == 200:
                csv_data = await response.text()
                print(f"✅ CSV download successful: {len(csv_data)} bytes")
                
                # Parse CSV for sensor data
                lines = csv_data.strip().split('\n')
                print(f"   CSV has {len(lines)} lines")
                
                if len(lines) > 1:
                    print("   Sample CSV data:")
                    for i, line in enumerate(lines[:3]):
                        print(f"   {i+1}: {line[:80]}...")
                
                # Extract today's data (what HA sensors would show)
                today = datetime.now().strftime("%-d/%-m/%Y")
                sensor_data = {
                    "current_rate": 0.25,
                    "next_rate": 0.25,
                    "solar_generation": 0.0,
                    "daily_consumption": 0.0,
                    "daily_feed_in": 0.0,
                    "average_daily_use": 0.0,
                }
                
                print(f"\n📊 Extracting sensor data for {today}...")
                
                for line in lines[1:]:  # Skip header
                    if not line.strip():
                        continue
                    
                    parts = line.split(',')
                    if len(parts) < 52:  # Need enough columns
                        continue
                    
                    try:
                        meter_element = parts[2]  # Feed-in or Consumption
                        date = parts[3]
                        
                        if date == today:
                            # Sum half-hour values (columns 4-51)
                            half_hour_values = []
                            for i in range(4, min(52, len(parts))):
                                try:
                                    value = float(parts[i])
                                    half_hour_values.append(value)
                                except ValueError:
                                    half_hour_values.append(0.0)
                            
                            daily_total = sum(half_hour_values)
                            
                            if meter_element == "Feed-in":
                                sensor_data["daily_feed_in"] = daily_total
                                # Current generation is latest non-zero value
                                for value in reversed(half_hour_values):
                                    if value > 0:
                                        sensor_data["solar_generation"] = value
                                        break
                                        
                            elif meter_element == "Consumption":
                                sensor_data["daily_consumption"] = daily_total
                            
                            print(f"   ✅ Processed {meter_element}: {daily_total:.2f} kWh")
                        
                    except (ValueError, IndexError) as e:
                        continue
                
                print("\n🎯 Final Sensor Values (what HA would show):")
                print("   📊 sensor.meridian_solar_current_rate:", f"{sensor_data['current_rate']:.2f} $/kWh")
                print("   📊 sensor.meridian_solar_next_rate:", f"{sensor_data['next_rate']:.2f} $/kWh") 
                print("   📊 sensor.meridian_solar_daily_consumption:", f"{sensor_data['daily_consumption']:.2f} kWh")
                print("   📊 sensor.meridian_solar_daily_feed_in:", f"{sensor_data['daily_feed_in']:.2f} kWh")
                print("   📊 sensor.meridian_solar_generation:", f"{sensor_data['solar_generation']:.2f} kW")
                print("   📊 sensor.meridian_solar_average_daily_use:", f"{sensor_data['average_daily_use']:.2f} kWh")
                
                # Determine if sensors will show data
                print("\n✅ HA Sensor Status Prediction:")
                if sensor_data['daily_consumption'] > 0:
                    print("   ✅ Daily Consumption: WILL SHOW DATA")
                else:
                    print("   ⚠️ Daily Consumption: May show 0 (check if data exists for today)")
                    
                if sensor_data['daily_feed_in'] > 0:
                    print("   ✅ Daily Feed In: WILL SHOW DATA")
                else:
                    print("   ⚠️ Daily Feed In: May show 0 (normal if no solar export today)")
                    
                if sensor_data['solar_generation'] > 0:
                    print("   ✅ Solar Generation: WILL SHOW DATA")
                else:
                    print("   ⚠️ Solar Generation: May show 0 (normal at night/low sun)")
                    
                print("   ✅ Rate sensors: WILL SHOW DATA (default values)")
                
            else:
                print(f"❌ CSV download failed: {response.status}")
        
        print("\n📋 Next Steps for Home Assistant:")
        print("1. Add the logging config to your configuration.yaml")
        print("2. Restart Home Assistant") 
        print("3. Check Settings → Integrations → Meridian Solar")
        print("4. Look at Settings → System → Logs for 'meridian_solar' entries")
        print("5. Sensors should update every 30 minutes")
    
    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(test_sensor_data_extraction())
