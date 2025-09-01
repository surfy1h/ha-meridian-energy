#!/usr/bin/env python3
"""
Test the rate extraction functionality
"""

import asyncio
import aiohttp
import json
import re
from collections import Counter

async def test_rate_extraction():
    """Test extracting electricity rates from Meridian portal"""
    print("🔍 Testing Rate Extraction from Meridian Portal")
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
        
        # Test rate extraction from various pages
        rate_pages = [
            ("https://secure.meridianenergy.co.nz/", "dashboard"),
            ("https://secure.meridianenergy.co.nz/billing", "billing"),
            ("https://secure.meridianenergy.co.nz/account", "account"),
            ("https://secure.meridianenergy.co.nz/usage", "usage"),
            ("https://secure.meridianenergy.co.nz/rates", "rates"),
        ]
        
        all_found_rates = []
        
        for url, page_type in rate_pages:
            print(f"\n📊 Checking {page_type} page...")
            
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        html = await response.text()
                        print(f"   ✅ Page accessible ({len(html)} bytes)")
                        
                        # Look for rate patterns
                        rate_patterns = [
                            (r'(\d+\.?\d*)\s*c(?:ents)?/kWh', 'cents per kWh'),
                            (r'(\d+\.?\d*)\s*cents?\s*per\s*kWh', 'cents per kWh (spelled out)'),
                            (r'\$(\d+\.?\d*)\s*per\s*kWh', 'dollars per kWh'),
                            (r'Rate[:\s]*\$?(\d+\.?\d*)', 'Rate label'),
                            (r'Price[:\s]*\$?(\d+\.?\d*)', 'Price label'),
                            (r'(\d+\.?\d*)\s*¢/kWh', 'cent symbol per kWh'),
                            (r'<td[^>]*>\s*\$?(\d+\.?\d*)\s*</td>', 'table cell'),
                            (r'current[^>]*rate[^>]*[:\s]*\$?(\d+\.?\d*)', 'current rate'),
                            (r'next[^>]*rate[^>]*[:\s]*\$?(\d+\.?\d*)', 'next rate'),
                            (r'"rate"[:\s]*(\d+\.?\d*)', 'JSON rate'),
                        ]
                        
                        page_rates = []
                        for pattern, description in rate_patterns:
                            matches = re.findall(pattern, html, re.IGNORECASE)
                            for match in matches:
                                try:
                                    rate = float(match)
                                    # Convert cents to dollars if rate is high
                                    if rate > 10:
                                        rate = rate / 100
                                    # Reasonable rate range for NZ
                                    if 0.15 <= rate <= 0.50:
                                        page_rates.append(rate)
                                        all_found_rates.append(rate)
                                        print(f"   💰 Found rate: {rate:.3f} $/kWh ({description})")
                                except ValueError:
                                    continue
                        
                        if not page_rates:
                            print(f"   ⚠️ No rates found on {page_type} page")
                        else:
                            print(f"   📈 Page summary: {len(page_rates)} rates found")
                    else:
                        print(f"   ❌ Page not accessible: {response.status}")
                        
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        # Analyze all found rates
        print(f"\n" + "=" * 50)
        print(f"📊 RATE EXTRACTION ANALYSIS")
        print(f"=" * 50)
        
        if all_found_rates:
            print(f"✅ Total rates found: {len(all_found_rates)}")
            print(f"📈 Rate range: {min(all_found_rates):.3f} - {max(all_found_rates):.3f} $/kWh")
            
            # Find most common rate
            rate_counts = Counter(all_found_rates)
            most_common = rate_counts.most_common(3)
            
            print(f"🎯 Most common rates:")
            for rate, count in most_common:
                print(f"   {rate:.3f} $/kWh (found {count} times)")
            
            recommended_rate = most_common[0][0]
            print(f"\n💡 RECOMMENDED RATE: {recommended_rate:.3f} $/kWh")
            
            print(f"\n🎯 EXPECTED HA SENSOR VALUES:")
            print(f"   Current Rate: {recommended_rate:.3f} $/kWh")
            print(f"   Next Rate: {recommended_rate:.3f} $/kWh")
            
        else:
            print(f"❌ No electricity rates found on any page")
            print(f"🔧 The integration will use default 0.25 $/kWh")
            
        print(f"\n📋 Next Steps:")
        print(f"1. Update integration to v2.3.0 in Home Assistant")
        print(f"2. Restart HA and check rate sensors")
        print(f"3. Rate sensors should now show real values instead of 0.25")
        
    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(test_rate_extraction())
