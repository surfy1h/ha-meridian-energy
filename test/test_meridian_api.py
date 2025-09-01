#!/usr/bin/env python3
"""
Test script for Meridian Energy Customer Portal
This script tests authentication and data retrieval from Meridian Energy's customer portal
"""

import asyncio
import aiohttp
import json
import sys
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urljoin, urlparse

# Customer Portal Configuration (will be updated by discovery)
BASE_URL = "https://secure.meridianenergy.co.nz"
LOGIN_URL = f"{BASE_URL}/login"
DASHBOARD_URL = f"{BASE_URL}/"
USAGE_URL = f"{BASE_URL}/"
BILLING_URL = f"{BASE_URL}/"

class MeridianPortalTester:
    """Test class for Meridian Energy Customer Portal"""
    
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session: Optional[aiohttp.ClientSession] = None
        self.logged_in = False
        self.csrf_token: Optional[str] = None
        self.form_action_url: Optional[str] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def discover_login_page(self) -> str:
        """Discover the correct login page URL"""
        print("🔍 Discovering login page...")
        
        # Try different common URL patterns
        potential_urls = [
            "https://secure.meridianenergy.co.nz/customers/",
            "https://secure.meridianenergy.co.nz/login",
            "https://secure.meridianenergy.co.nz/",
            "https://www.meridianenergy.co.nz/login",
            "https://www.meridianenergy.co.nz/customers/login",
            "https://my.meridianenergy.co.nz/",
            "https://portal.meridianenergy.co.nz/",
        ]
        
        for url in potential_urls:
            try:
                async with self.session.get(url, allow_redirects=True) as response:
                    print(f"   Trying {url}: {response.status}")
                    
                    if response.status == 200:
                        html = await response.text()
                        # Look for login indicators
                        login_indicators = ['password', 'username', 'login', 'sign in', 'email']
                        found_indicators = sum(1 for indicator in login_indicators if indicator.lower() in html.lower())
                        
                        if found_indicators >= 2:  # Need at least 2 login indicators
                            print(f"   ✅ Found login page at: {url}")
                            return str(response.url)  # Return the final URL after redirects
                            
            except Exception as e:
                print(f"   ❌ Error checking {url}: {e}")
                continue
        
        print("   ❌ No valid login page found")
        return ""

    async def get_login_page(self) -> bool:
        """Get the login page and extract CSRF token"""
        print("🌐 Getting login page...")
        
        # First discover the correct login URL
        discovered_url = await self.discover_login_page()
        if not discovered_url:
            return False
        
        # Update our URLs based on discovery
        global LOGIN_URL, DASHBOARD_URL, USAGE_URL, BILLING_URL
        base_url = discovered_url.rsplit('/', 1)[0] if discovered_url.endswith('/') else discovered_url.rsplit('/', 1)[0]
        LOGIN_URL = discovered_url
        DASHBOARD_URL = f"{base_url}/"
        USAGE_URL = f"{base_url}/"
        BILLING_URL = f"{base_url}/"
        
        try:
            async with self.session.get(LOGIN_URL) as response:
                print(f"   Status: {response.status}")
                
                if response.status == 200:
                    html = await response.text()
                    
                    # Look for CSRF token in various common formats
                    csrf_patterns = [
                        r'name="_token"\s+value="([^"]+)"',
                        r'name="csrf_token"\s+value="([^"]+)"',
                        r'name="authenticity_token"\s+value="([^"]+)"',
                        r'"csrf_token":"([^"]+)"',
                        r'_token["\']:\s*["\']([^"\']+)["\']'
                    ]
                    
                    for pattern in csrf_patterns:
                        match = re.search(pattern, html, re.IGNORECASE)
                        if match:
                            self.csrf_token = match.group(1)
                            print(f"   ✅ Found CSRF token: {self.csrf_token[:20]}...")
                            break
                    
                    if not self.csrf_token:
                        print("   ⚠️  No CSRF token found, proceeding without it")
                    
                    # Debug: Look for form field names and action
                    form_fields = re.findall(r'<input[^>]*name=["\']([^"\']+)["\'][^>]*>', html, re.IGNORECASE)
                    if form_fields:
                        print(f"   🔍 Found form fields: {form_fields[:5]}")  # Show first 5
                    
                    # Look for form action
                    form_action = re.search(r'<form[^>]*action=["\']([^"\']+)["\']', html, re.IGNORECASE)
                    if form_action:
                        action_url = form_action.group(1)
                        print(f"   🎯 Form action: {action_url}")
                        # Store the correct action URL for later use
                        self.form_action_url = urljoin(LOGIN_URL, action_url) if action_url.startswith('/') else action_url
                        print(f"   🔄 Will submit to: {self.form_action_url}")
                    else:
                        print(f"   ⚠️  No form action found, using current URL")
                        self.form_action_url = LOGIN_URL
                    
                    return True
                else:
                    print(f"   ❌ Failed to get login page: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"   ❌ Login page error: {e}")
            return False

    async def test_authentication(self) -> bool:
        """Test authentication with Meridian Customer Portal"""
        print("🔐 Testing authentication...")
        
        # First get the login page
        if not await self.get_login_page():
            return False
        
        try:
            # Prepare login data with correct field names
            login_data = {
                "email": self.username,
                "password": self.password,
                "commit": "Sign in",  # Submit button value
            }
            
            # Add CSRF token if we found one
            if self.csrf_token:
                login_data["authenticity_token"] = self.csrf_token
            
            # Set headers to mimic a browser
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": LOGIN_URL,
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            # Use the correct form action URL
            submit_url = self.form_action_url or LOGIN_URL
            print(f"   📤 Submitting to: {submit_url}")
            
            async with self.session.post(submit_url, data=login_data, headers=headers, allow_redirects=False) as response:
                print(f"   Status: {response.status}")
                
                # Debug: Show response headers
                location = response.headers.get('Location', '')
                if location:
                    print(f"   🔄 Redirect to: {location}")
                
                # Check for successful login (redirect or 200 with success indicators)
                if response.status in [200, 302, 303]:
                    response_text = await response.text()
                    
                    # Debug: Show first part of response
                    print(f"   📄 Response preview: {response_text[:200]}...")
                    
                    if (response.status in [302, 303] and 
                        ('dashboard' in location.lower() or 'customers' in location.lower() or 
                         'home' in location.lower() or location == '/')):
                        print(f"   ✅ Authentication successful (redirected to: {location})")
                        self.logged_in = True
                        return True
                    elif 'dashboard' in response_text.lower() or 'welcome' in response_text.lower():
                        print(f"   ✅ Authentication successful")
                        self.logged_in = True
                        return True
                    elif 'invalid' in response_text.lower() or 'incorrect' in response_text.lower():
                        print(f"   ❌ Authentication failed: Invalid credentials")
                        return False
                    elif response.status in [302, 303]:
                        # Follow the redirect to see where it goes
                        print(f"   🔄 Following redirect to check result...")
                        try:
                            async with self.session.get(urljoin(LOGIN_URL, location), headers=headers) as redirect_response:
                                redirect_text = await redirect_response.text()
                                if ('dashboard' in redirect_text.lower() or 'welcome' in redirect_text.lower() or
                                    'account' in redirect_text.lower()):
                                    print(f"   ✅ Authentication successful (confirmed via redirect)")
                                    self.logged_in = True
                                    return True
                        except Exception as e:
                            print(f"   ⚠️  Error following redirect: {e}")
                    
                    print(f"   ⚠️  Uncertain login result, checking dashboard access...")
                    # Try to access dashboard to confirm login
                    self.logged_in = True  # Assume success for now
                    return await self.test_dashboard_access()
                else:
                    error_text = await response.text()
                    print(f"   ❌ Authentication failed: {error_text[:200]}...")
                    return False
                    
        except Exception as e:
            print(f"   ❌ Authentication error: {e}")
            return False
    
    async def test_dashboard_access(self) -> bool:
        """Test accessing the customer dashboard"""
        print("\n📋 Testing dashboard access...")
        
        if not self.logged_in:
            print("   ❌ Not logged in")
            return False
            
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": LOGIN_URL
            }
            
            async with self.session.get(DASHBOARD_URL, headers=headers) as response:
                print(f"   Status: {response.status}")
                
                if response.status == 200:
                    html = await response.text()
                    
                    # Look for indicators that we're on the dashboard
                    dashboard_indicators = [
                        'dashboard', 'account', 'usage', 'billing', 'solar',
                        'current balance', 'recent activity', 'meter reading'
                    ]
                    
                    found_indicators = []
                    for indicator in dashboard_indicators:
                        if indicator.lower() in html.lower():
                            found_indicators.append(indicator)
                    
                    if found_indicators:
                        print(f"   ✅ Dashboard access successful")
                        print(f"   Found indicators: {', '.join(found_indicators[:3])}...")
                        return True
                    else:
                        print(f"   ❌ Dashboard access failed - no expected content found")
                        return False
                else:
                    print(f"   ❌ Dashboard access failed: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"   ❌ Dashboard access error: {e}")
            return False
    
    async def test_get_usage_data(self) -> bool:
        """Test getting usage/billing data from usage chart page"""
        print("\n💰 Testing usage data retrieval...")
        
        if not self.logged_in:
            print("   ❌ Not logged in")
            return False
            
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": DASHBOARD_URL
            }
            
            # Check the specific usage chart page
            usage_chart_url = "https://secure.meridianenergy.co.nz/usage"
            print(f"   🔍 Checking usage chart: {usage_chart_url}")
            
            async with self.session.get(usage_chart_url, headers=headers) as response:
                print(f"   Status: {response.status}")
                
                if response.status == 200:
                    html = await response.text()
                    
                    # Look for usage chart indicators
                    usage_indicators = [
                        'average daily use', 'daily usage', 'usage chart', 'power usage',
                        'consumption', 'kwh', 'daily average', 'usage pattern'
                    ]
                    
                    found_indicators = []
                    for indicator in usage_indicators:
                        if indicator.lower() in html.lower():
                            found_indicators.append(indicator)
                    
                    if found_indicators:
                        print(f"   ✅ Usage chart page accessible")
                        print(f"   Found indicators: {', '.join(found_indicators[:5])}...")
                        
                        # Look for specific usage data patterns
                        usage_patterns = [
                            r'average\s*daily\s*use[:\s]*(\d+\.?\d*)\s*kWh',  # Average daily use
                            r'daily\s*average[:\s]*(\d+\.?\d*)\s*kWh',  # Daily average
                            r'(\d+\.?\d*)\s*kWh\s*per\s*day',  # kWh per day
                            r'(\d+\.?\d*)\s*kWh',  # General kWh values
                            r'\$(\d+\.?\d*)',      # Dollar amounts
                            r'usage[:\s]*(\d+\.?\d*)\s*kWh'  # Usage amounts
                        ]
                        
                        found_data = {}
                        for i, pattern in enumerate(usage_patterns):
                            matches = re.findall(pattern, html, re.IGNORECASE)
                            if matches:
                                found_data[f"usage_pattern_{i}"] = matches[:5]  # First 5 matches
                        
                        if found_data:
                            print(f"   📊 Usage data patterns found:")
                            for key, values in found_data.items():
                                print(f"   {key}: {values}")
                        
                        # Look for chart data endpoints
                        chart_patterns = [
                            r'data[:\s]*\[([^\]]+)\]',  # Data arrays
                            r'graphene_data_\d+',  # Graphene data IDs
                            r'usage_data["\']?\s*[:=]\s*["\']?([^"\';\s]+)',  # Usage data variables
                        ]
                        
                        for i, pattern in enumerate(chart_patterns):
                            matches = re.findall(pattern, html, re.IGNORECASE)
                            if matches:
                                print(f"   📈 Chart data pattern {i}: {matches[:2]}")  # First 2 matches
                        
                        return True
                    else:
                        print(f"   ⚠️  Usage chart page accessible but no usage indicators found")
                        return False
                        
                elif response.status == 404:
                    print(f"   ❌ Usage chart page not found")
                    return False
                else:
                    print(f"   ❌ Failed to access usage chart: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"   ❌ Usage data retrieval error: {e}")
            return False
    
    async def test_get_solar_data(self) -> bool:
        """Test getting solar generation data from the feed-in report page"""
        print("\n☀️ Testing solar data retrieval...")
        
        if not self.logged_in:
            print("   ❌ Not logged in")
            return False
            
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": DASHBOARD_URL
            }
            
            # Check the specific feed-in report page
            feed_in_url = "https://secure.meridianenergy.co.nz/feed_in_report"
            print(f"   🔍 Checking feed-in report: {feed_in_url}")
            
            async with self.session.get(feed_in_url, headers=headers) as response:
                print(f"   Status: {response.status}")
                
                if response.status == 200:
                    html = await response.text()
                    
                    # Look for solar/feed-in specific indicators
                    solar_indicators = [
                        'feed in', 'feed-in', 'solar', 'generation', 'export', 
                        'heatmap', 'csv', 'download', 'kwh', 'half hour'
                    ]
                    
                    found_indicators = []
                    for indicator in solar_indicators:
                        if indicator.lower() in html.lower():
                            found_indicators.append(indicator)
                    
                    if found_indicators:
                        print(f"   ✅ Feed-in report page accessible")
                        print(f"   Found indicators: {', '.join(found_indicators[:5])}...")
                        
                        # Look for specific solar data patterns
                        solar_patterns = [
                            r'(\d+\.?\d*)\s*kWh',  # kWh values
                            r'feed.?in[:\s]*\$?(\d+\.?\d*)',  # Feed-in amounts
                            r'export[:\s]*(\d+\.?\d*)',  # Export amounts
                            r'generation[:\s]*(\d+\.?\d*)',  # Generation amounts
                            r'total[:\s]*(\d+\.?\d*)',  # Total amounts
                        ]
                        
                        found_data = {}
                        for i, pattern in enumerate(solar_patterns):
                            matches = re.findall(pattern, html, re.IGNORECASE)
                            if matches:
                                found_data[f"solar_pattern_{i}"] = matches[:5]  # First 5 matches
                        
                        if found_data:
                            print(f"   📊 Solar data patterns found:")
                            for key, values in found_data.items():
                                print(f"   {key}: {values}")
                        
                        # Look for CSV download link
                        csv_patterns = [
                            r'href=["\']([^"\']*\.csv[^"\']*)["\']',
                            r'href=["\']([^"\']*download[^"\']*)["\']',
                            r'href=["\']([^"\']*export[^"\']*)["\']'
                        ]
                        
                        for pattern in csv_patterns:
                            matches = re.findall(pattern, html, re.IGNORECASE)
                            if matches:
                                print(f"   📥 Found potential CSV download: {matches[0]}")
                                break
                        
                        return True
                    else:
                        print(f"   ⚠️  Feed-in report page accessible but no solar indicators found")
                        return False
                        
                elif response.status == 404:
                    print(f"   ❌ Feed-in report page not found - account may not have solar")
                    return False
                else:
                    print(f"   ❌ Failed to access feed-in report: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"   ❌ Solar data retrieval error: {e}")
            return False

    async def test_csv_download(self) -> bool:
        """Test downloading CSV data from feed-in report"""
        print("\n📥 Testing CSV download...")
        
        if not self.logged_in:
            print("   ❌ Not logged in")
            return False
            
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": "https://secure.meridianenergy.co.nz/feed_in_report"
            }
            
            # Try common CSV download URLs
            csv_urls = [
                "https://secure.meridianenergy.co.nz/feed_in_report.csv",
                "https://secure.meridianenergy.co.nz/feed_in_report/download",
                "https://secure.meridianenergy.co.nz/feed_in_report/export",
                "https://secure.meridianenergy.co.nz/customers/feed_in_report.csv"
            ]
            
            for csv_url in csv_urls:
                try:
                    async with self.session.get(csv_url, headers=headers) as response:
                        print(f"   Trying {csv_url}: {response.status}")
                        
                        if response.status == 200:
                            content_type = response.headers.get('content-type', '')
                            if 'csv' in content_type.lower() or 'text' in content_type.lower():
                                csv_data = await response.text()
                                lines = csv_data.split('\n')[:5]  # First 5 lines
                                print(f"   ✅ CSV download successful!")
                                print(f"   Content-Type: {content_type}")
                                print(f"   First few lines:")
                                for i, line in enumerate(lines):
                                    if line.strip():
                                        print(f"   {i+1}: {line[:100]}...")  # First 100 chars
                                return True
                                
                except Exception as e:
                    print(f"   ⚠️  Error trying {csv_url}: {e}")
                    continue
            
            print(f"   ❌ No CSV download found")
            return False
                    
        except Exception as e:
            print(f"   ❌ CSV download error: {e}")
            return False
    
    async def test_find_data_endpoints(self) -> bool:
        """Test finding potential data endpoints or AJAX calls"""
        print(f"\n📊 Testing for data endpoints...")
        
        if not self.logged_in:
            print("   ❌ Not logged in")
            return False
            
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": DASHBOARD_URL
            }
            
            # Check dashboard for JavaScript/AJAX endpoints
            async with self.session.get(DASHBOARD_URL, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    
                    # Look for potential API endpoints in JavaScript
                    endpoint_patterns = [
                        r'["\']([^"\']*api[^"\']*)["\']',  # API URLs
                        r'["\']([^"\']*ajax[^"\']*)["\']',  # AJAX URLs
                        r'["\']([^"\']*data[^"\']*)["\']',  # Data URLs
                        r'fetch\(["\']([^"\']+)["\']',  # Fetch calls
                        r'\.get\(["\']([^"\']+)["\']',  # GET calls
                        r'url[:\s]*["\']([^"\']+)["\']'  # URL definitions
                    ]
                    
                    found_endpoints = set()
                    for pattern in endpoint_patterns:
                        matches = re.findall(pattern, html, re.IGNORECASE)
                        for match in matches:
                            if ('meridian' in match.lower() or 
                                match.startswith('/') or 
                                'api' in match.lower() or 
                                'data' in match.lower()):
                                found_endpoints.add(match)
                    
                    if found_endpoints:
                        print(f"   ✅ Found potential endpoints:")
                        for endpoint in list(found_endpoints)[:10]:  # Show first 10
                            print(f"   - {endpoint}")
                        return True
                    else:
                        print(f"   ⚠️  No obvious data endpoints found")
                        return False
                else:
                    print(f"   ❌ Failed to analyze dashboard: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"   ❌ Endpoint discovery error: {e}")
            return False
    
    async def run_all_tests(self) -> Dict[str, bool]:
        """Run all portal tests"""
        print("🚀 Starting Meridian Energy Portal Tests")
        print("=" * 50)
        
        results = {}
        
        # Test authentication
        results["authentication"] = await self.test_authentication()
        
        if results["authentication"]:
            # Test dashboard access
            results["dashboard"] = await self.test_dashboard_access()
            
            # Test usage data
            results["usage_data"] = await self.test_get_usage_data()
            
            # Test solar data
            results["solar_data"] = await self.test_get_solar_data()
            
            # Test CSV download if solar data is available
            if results["solar_data"]:
                results["csv_download"] = await self.test_csv_download()
            else:
                results["csv_download"] = False
            
            # Test endpoint discovery
            results["data_endpoints"] = await self.test_find_data_endpoints()
        else:
            results["dashboard"] = False
            results["usage_data"] = False
            results["solar_data"] = False
            results["csv_download"] = False
            results["data_endpoints"] = False
        
        return results

def load_config() -> Dict[str, Any]:
    """Load configuration from config.json if it exists"""
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"⚠️  Warning: Invalid JSON in config.json: {e}")
        return {}

async def main():
    """Main test function"""
    print("Meridian Energy API Tester")
    print("=" * 30)
    
    # Try to load config first
    config = load_config()
    
    # Get credentials from various sources
    if len(sys.argv) >= 3:
        username = sys.argv[1]
        password = sys.argv[2]
    elif config.get("username") and config.get("password"):
        username = config["username"]
        password = config["password"]
        print("📁 Using credentials from config.json")
    else:
        print("💡 Tip: You can create a config.json file with your credentials")
        print("   or pass them as arguments: python3 test_meridian_api.py username password")
        print()
        username = input("Enter your Meridian Energy username: ")
        password = input("Enter your Meridian Energy password: ")
    
    if not username or not password:
        print("❌ Username and password are required")
        return
    
    # Run tests
    async with MeridianPortalTester(username, password) as tester:
        results = await tester.run_all_tests()
        
        # Print summary
        print("\n" + "=" * 50)
        print("📋 Test Results Summary:")
        print("=" * 50)
        
        for test_name, success in results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"   {test_name.replace('_', ' ').title()}: {status}")
        
        total_tests = len(results)
        passed_tests = sum(results.values())
        
        print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            print("🎉 All tests passed! The portal integration should work correctly.")
        elif results.get("authentication"):
            print("✅ Authentication works! Some data extraction may need refinement.")
        else:
            print("⚠️  Authentication failed. Check your credentials or the portal structure.")

if __name__ == "__main__":
    asyncio.run(main())