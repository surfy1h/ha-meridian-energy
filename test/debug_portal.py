#!/usr/bin/env python3
"""
Debug script to explore Meridian Energy portal structure
This helps identify the correct URLs and data patterns for your specific account
"""

import asyncio
import aiohttp
import json
import re
from test_meridian_api import MeridianPortalTester

async def debug_portal_structure():
    """Debug the portal structure to find data sources"""
    
    # Load config
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ Please create config.json with your credentials first")
        return
    
    async with MeridianPortalTester(config["username"], config["password"]) as tester:
        print("🔍 Debugging Meridian Portal Structure")
        print("=" * 50)
        
        # Test authentication
        if not await tester.test_authentication():
            print("❌ Authentication failed")
            return
        
        print("✅ Authentication successful")
        print("\n🌐 Exploring portal pages...")
        
        # Common page patterns to check
        pages_to_check = [
            "/",
            "/dashboard",
            "/account",
            "/usage",
            "/usage/chart",
            "/usage/data",
            "/billing",
            "/bills",
            "/solar",
            "/feed_in",
            "/feed_in_report",
            "/generation",
            "/export",
            "/reports",
            "/data",
            "/download",
        ]
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://secure.meridianenergy.co.nz/"
        }
        
        found_pages = []
        
        for page in pages_to_check:
            try:
                url = f"https://secure.meridianenergy.co.nz{page}"
                async with tester._session.get(url, headers=headers) as response:
                    if response.status == 200:
                        html = await response.text()
                        
                        # Look for energy-related keywords
                        keywords = ['kwh', 'solar', 'generation', 'consumption', 'usage', 'feed', 'export', 'chart', 'data']
                        found_keywords = [k for k in keywords if k.lower() in html.lower()]
                        
                        if found_keywords:
                            found_pages.append({
                                'url': url,
                                'keywords': found_keywords,
                                'length': len(html)
                            })
                            print(f"   ✅ {url} - Keywords: {', '.join(found_keywords)}")
                        else:
                            print(f"   ⚪ {url} - No energy keywords")
                    else:
                        print(f"   ❌ {url} - Status: {response.status}")
                        
            except Exception as e:
                print(f"   ⚠️  {url} - Error: {e}")
        
        print(f"\n📊 Summary: Found {len(found_pages)} relevant pages")
        
        # Check for specific data patterns in promising pages
        if found_pages:
            print("\n🔍 Analyzing promising pages for data patterns...")
            
            for page in found_pages[:3]:  # Check top 3 most promising
                try:
                    async with tester._session.get(page['url'], headers=headers) as response:
                        if response.status == 200:
                            html = await response.text()
                            
                            print(f"\n📄 {page['url']}:")
                            
                            # Look for numbers with kWh
                            kwh_pattern = r'(\d+\.?\d*)\s*kWh'
                            kwh_matches = re.findall(kwh_pattern, html, re.IGNORECASE)
                            if kwh_matches:
                                print(f"   💡 kWh values found: {kwh_matches[:5]}")
                            
                            # Look for dollar amounts
                            dollar_pattern = r'\$(\d+\.?\d*)'
                            dollar_matches = re.findall(dollar_pattern, html, re.IGNORECASE)
                            if dollar_matches:
                                print(f"   💰 Dollar amounts: {dollar_matches[:5]}")
                            
                            # Look for charts/data endpoints
                            chart_pattern = r'(chart|data|api)["\'\s]*[:=]["\'\s]*([^"\';\s]+)'
                            chart_matches = re.findall(chart_pattern, html, re.IGNORECASE)
                            if chart_matches:
                                print(f"   📈 Chart/data endpoints: {chart_matches[:3]}")
                            
                            # Look for download links
                            download_pattern = r'href=["\']([^"\']*(?:download|export|csv)[^"\']*)["\']'
                            download_matches = re.findall(download_pattern, html, re.IGNORECASE)
                            if download_matches:
                                print(f"   📥 Download links: {download_matches[:3]}")
                                
                except Exception as e:
                    print(f"   ⚠️  Error analyzing {page['url']}: {e}")
        
        print("\n" + "=" * 50)
        print("🎯 Next Steps:")
        print("1. Check if any of the found pages show your usage/solar data")
        print("2. Look for different navigation in your actual portal")
        print("3. Verify your account has solar features enabled")
        print("4. Share this output for integration updates")

if __name__ == "__main__":
    asyncio.run(debug_portal_structure())
