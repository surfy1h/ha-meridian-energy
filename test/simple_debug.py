#!/usr/bin/env python3
"""
Simple debug script to check what's available in your Meridian portal
"""

import asyncio
import aiohttp
import json
import re

async def check_portal_pages():
    """Check what pages are available in your portal"""
    
    # Load config
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ Please update config.json with your real credentials first")
        return
    
    print("🔍 Checking Meridian Portal Pages")
    print("=" * 40)
    
    async with aiohttp.ClientSession() as session:
        # Step 1: Get login page and token
        print("🌐 Getting login page...")
        async with session.get("https://secure.meridianenergy.co.nz/login") as response:
            if response.status != 200:
                print(f"❌ Can't access login page: {response.status}")
                return
            
            html = await response.text()
            
            # Extract CSRF token
            token_match = re.search(r'name="authenticity_token"\s+value="([^"]+)"', html)
            if not token_match:
                print("❌ Can't find CSRF token")
                return
            
            csrf_token = token_match.group(1)
            print(f"✅ Got CSRF token: {csrf_token[:20]}...")
        
        # Step 2: Login
        print("🔐 Logging in...")
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
        
        # Step 3: Check dashboard and look for navigation
        print("\n📋 Checking dashboard...")
        async with session.get("https://secure.meridianenergy.co.nz/", headers=headers) as response:
            if response.status == 200:
                html = await response.text()
                print("✅ Dashboard accessible")
                
                # Look for navigation links
                nav_links = re.findall(r'href="([^"]*(?:usage|solar|feed|report|bill|account)[^"]*)"', html, re.IGNORECASE)
                if nav_links:
                    print(f"🔗 Found navigation links: {nav_links}")
                
                # Look for any mention of solar/kwh/generation
                solar_keywords = ['solar', 'generation', 'kwh', 'feed', 'export', 'import']
                found_keywords = []
                for keyword in solar_keywords:
                    if keyword.lower() in html.lower():
                        found_keywords.append(keyword)
                
                if found_keywords:
                    print(f"☀️ Solar keywords found: {found_keywords}")
                else:
                    print("⚠️ No solar keywords found on dashboard")
        
        # Step 4: Test specific pages
        print("\n🧪 Testing specific pages...")
        test_pages = [
            "/usage",
            "/solar", 
            "/feed_in_report",
            "/generation",
            "/reports",
            "/billing",
            "/account"
        ]
        
        for page in test_pages:
            url = f"https://secure.meridianenergy.co.nz{page}"
            try:
                async with session.get(url, headers=headers) as response:
                    status = "✅" if response.status == 200 else "❌"
                    print(f"   {status} {url} - Status: {response.status}")
                    
                    if response.status == 200:
                        html = await response.text()
                        
                        # Look for energy data
                        kwh_matches = re.findall(r'(\d+\.?\d*)\s*kWh', html, re.IGNORECASE)
                        if kwh_matches:
                            print(f"      💡 Found kWh values: {kwh_matches[:3]}")
                        
                        # Look for dollar amounts  
                        dollar_matches = re.findall(r'\$(\d+\.?\d*)', html)
                        if dollar_matches:
                            print(f"      💰 Found dollar amounts: {dollar_matches[:3]}")
                        
                        # Look for download links
                        download_links = re.findall(r'href="([^"]*(?:download|export|csv)[^"]*)"', html, re.IGNORECASE)
                        if download_links:
                            print(f"      📥 Download links: {download_links}")
                            
            except Exception as e:
                print(f"   ⚠️ {url} - Error: {e}")
        
        print("\n" + "=" * 40)
        print("🎯 Please share this output so we can fix the integration!")

if __name__ == "__main__":
    asyncio.run(check_portal_pages())
