#!/usr/bin/env python3
"""
Test the enhanced aggressive data extraction approach
This mimics what the updated integration will do
"""

import asyncio
import aiohttp
import json
import re
from datetime import datetime

async def test_enhanced_extraction():
    """Test enhanced data extraction like the updated integration"""
    
    # Load config
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ Please create config.json with your real credentials first")
        print("Copy config.example.json to config.json and update with your credentials")
        return
    
    print("🚀 Testing Enhanced Meridian Integration (v2.3.0)")
    print("=" * 60)
    
    session = aiohttp.ClientSession()
    
    try:
        # Step 1: Login (reusing the working login logic)
        print("🔐 Logging in...")
        async with session.get("https://secure.meridianenergy.co.nz/login") as response:
            if response.status != 200:
                print(f"❌ Can't access login page: {response.status}")
                return
            
            html = await response.text()
            token_match = re.search(r'name="authenticity_token"\s+value="([^"]+)"', html)
            if not token_match:
                print("❌ Can't find CSRF token")
                return
            
            csrf_token = token_match.group(1)
            print(f"✅ Got CSRF token")
        
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
            
            if response.status not in [200, 302, 303]:
                print(f"❌ Login failed: {response.status}")
                return
            
            print("✅ Login successful!")
        
        # Step 2: Aggressive CSV Download (15+ URLs)
        print("\n📥 Testing Aggressive CSV Download...")
        
        csv_urls = [
            "https://secure.meridianenergy.co.nz/feed_in_report.csv",
            "https://secure.meridianenergy.co.nz/feed_in_report/download",
            "https://secure.meridianenergy.co.nz/feed_in_report/export",
            "https://secure.meridianenergy.co.nz/customers/feed_in_report.csv",
            "https://secure.meridianenergy.co.nz/usage.csv",
            "https://secure.meridianenergy.co.nz/usage/download", 
            "https://secure.meridianenergy.co.nz/usage/export",
            "https://secure.meridianenergy.co.nz/data/download",
            "https://secure.meridianenergy.co.nz/data/export",
            "https://secure.meridianenergy.co.nz/reports/download",
            "https://secure.meridianenergy.co.nz/reports/export",
            "https://secure.meridianenergy.co.nz/solar/download",
            "https://secure.meridianenergy.co.nz/solar/export",
            "https://secure.meridianenergy.co.nz/generation/download",
            "https://secure.meridianenergy.co.nz/generation/export"
        ]
        
        csv_found = False
        for csv_url in csv_urls:
            try:
                async with session.get(csv_url, headers=headers) as response:
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        csv_data = await response.text()
                        
                        # Enhanced CSV detection
                        if ('csv' in content_type.lower() or 'text' in content_type.lower() or 
                            'application/octet-stream' in content_type.lower() or
                            ',' in csv_data or 'Date,Time' in csv_data or 'Feed-in' in csv_data or
                            'Consumption' in csv_data or len(csv_data) > 100):
                            
                            lines = csv_data.split('\n')[:5]
                            if any(',' in line for line in lines if line.strip()):
                                print(f"✅ Found CSV at: {csv_url}")
                                print(f"   Content-Type: {content_type}")
                                print(f"   Data size: {len(csv_data)} bytes")
                                print(f"   Sample lines:")
                                for i, line in enumerate(lines):
                                    if line.strip():
                                        print(f"   {i+1}: {line[:80]}...")
                                csv_found = True
                                break
                    else:
                        print(f"   ❌ {csv_url}: {response.status}")
                        
            except Exception as e:
                print(f"   ⚠️ {csv_url}: {e}")
        
        if not csv_found:
            print("❌ No CSV data found")
        
        # Step 3: Aggressive Page Scraping
        print("\n🔍 Testing Aggressive Page Scraping...")
        
        pages_to_scrape = [
            ("https://secure.meridianenergy.co.nz/", "dashboard"),
            ("https://secure.meridianenergy.co.nz/usage", "usage"),
            ("https://secure.meridianenergy.co.nz/feed_in_report", "feed_in"),
            ("https://secure.meridianenergy.co.nz/billing", "billing"),
            ("https://secure.meridianenergy.co.nz/account", "account"),
        ]
        
        found_data = {
            "kwh_values": [],
            "dollar_values": [],
            "energy_patterns": []
        }
        
        for url, page_type in pages_to_scrape:
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        html = await response.text()
                        print(f"✅ Scraped {page_type} page ({len(html)} bytes)")
                        
                        # Extract kWh values
                        kwh_matches = re.findall(r'(\d+\.?\d*)\s*kWh', html, re.IGNORECASE)
                        if kwh_matches:
                            found_data["kwh_values"].extend(kwh_matches[:3])
                            print(f"   💡 kWh values: {kwh_matches[:3]}")
                        
                        # Extract dollar amounts
                        dollar_matches = re.findall(r'\$(\d+\.?\d*)', html)
                        if dollar_matches:
                            found_data["dollar_values"].extend(dollar_matches[:3])
                            print(f"   💰 Dollar amounts: {dollar_matches[:3]}")
                        
                        # Look for energy patterns
                        energy_patterns = [
                            r'generation[:\s]*(\d+\.?\d*)',
                            r'solar[:\s]*(\d+\.?\d*)',
                            r'feed.?in[:\s]*(\d+\.?\d*)',
                            r'export[:\s]*(\d+\.?\d*)',
                            r'consumption[:\s]*(\d+\.?\d*)',
                        ]
                        
                        for pattern in energy_patterns:
                            matches = re.findall(pattern, html, re.IGNORECASE)
                            if matches:
                                found_data["energy_patterns"].extend(matches[:2])
                                print(f"   ⚡ Energy pattern ({pattern}): {matches[:2]}")
                    else:
                        print(f"   ❌ {page_type}: {response.status}")
                        
            except Exception as e:
                print(f"   ⚠️ {page_type}: {e}")
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 Data Extraction Summary:")
        print("=" * 60)
        
        if csv_found:
            print("✅ CSV Download: SUCCESS")
        else:
            print("❌ CSV Download: FAILED")
        
        if found_data["kwh_values"]:
            print(f"✅ kWh Values Found: {len(found_data['kwh_values'])} values")
        else:
            print("❌ kWh Values: NONE FOUND")
        
        if found_data["dollar_values"]:
            print(f"✅ Dollar Values Found: {len(found_data['dollar_values'])} values")
        else:
            print("❌ Dollar Values: NONE FOUND")
        
        if found_data["energy_patterns"]:
            print(f"✅ Energy Patterns Found: {len(found_data['energy_patterns'])} patterns")
        else:
            print("❌ Energy Patterns: NONE FOUND")
        
        print("\n🎯 Expected Results in Home Assistant:")
        if csv_found or found_data["kwh_values"] or found_data["energy_patterns"]:
            print("✅ Sensors should now show data!")
            print("✅ The integration has much better data detection now")
        else:
            print("⚠️ May still have issues - your portal might use different data format")
            print("🔧 Please share this output for further customization")
    
    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(test_enhanced_extraction())
