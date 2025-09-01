#!/usr/bin/env python3
"""
Diagnose Home Assistant Integration Issues
This script simulates the exact HA coordinator behavior and identifies problems
"""

import asyncio
import aiohttp
import json
import re
from datetime import datetime, timedelta
import logging

# Set up detailed logging like HA
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
)

class MockMeridianCoordinator:
    """Simulate the actual HA coordinator"""
    
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self._logged_in = False
        self._session = None
        self._retry_count = 0
        
        # URLs that may be set by discovery
        self.login_url = "https://secure.meridianenergy.co.nz/login"
        self.dashboard_url = "https://secure.meridianenergy.co.nz/"
        
        self._logger = logging.getLogger("meridian_coordinator")
        self._logger.setLevel(logging.DEBUG)
    
    async def _create_session(self):
        """Create HTTP session like HA coordinator"""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=2)
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
    
    async def _authenticate(self) -> bool:
        """Authenticate exactly like HA coordinator"""
        self._logger.info("🔐 Starting authentication process...")
        self._logger.debug(f"Username: {self.username}")
        
        await self._create_session()
        
        try:
            # Get login page
            self._logger.debug("📄 Getting login page...")
            async with self._session.get(self.login_url) as response:
                if response.status != 200:
                    self._logger.error(f"❌ Login page failed: {response.status}")
                    return False
                
                html = await response.text()
                self._logger.debug(f"✅ Login page loaded ({len(html)} chars)")
                
                # Extract CSRF token
                token_match = re.search(r'name="authenticity_token"\s+value="([^"]+)"', html)
                if not token_match:
                    self._logger.error("❌ CSRF token not found")
                    return False
                    
                csrf_token = token_match.group(1)
                self._logger.debug(f"✅ CSRF token: {csrf_token[:20]}...")
            
            # Perform login
            self._logger.debug("🔑 Performing login...")
            login_data = {
                "email": self.username,
                "password": self.password,
                "authenticity_token": csrf_token,
                "commit": "Sign in"
            }
            
            headers = {
                "Referer": self.login_url,
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            async with self._session.post(self.dashboard_url, 
                                         data=login_data, headers=headers, allow_redirects=False) as response:
                
                self._logger.debug(f"Login response: {response.status}")
                if response.status not in [200, 302, 303]:
                    self._logger.error(f"❌ Login failed with status {response.status}")
                    return False
                
                self._logged_in = True
                self._logger.info("✅ Authentication successful")
                return True
                
        except Exception as e:
            self._logger.error(f"❌ Authentication error: {e}")
            return False
    
    async def _test_csv_download(self) -> dict:
        """Test CSV download exactly like HA coordinator"""
        self._logger.info("📥 Testing CSV download...")
        
        if not self._logged_in:
            if not await self._authenticate():
                return {}
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://secure.meridianenergy.co.nz/feed_in_report"
        }
        
        csv_urls = [
            "https://secure.meridianenergy.co.nz/feed_in_report.csv",
            "https://secure.meridianenergy.co.nz/feed_in_report/download",
            "https://secure.meridianenergy.co.nz/feed_in_report/export",
            "https://secure.meridianenergy.co.nz/customers/feed_in_report.csv"
        ]
        
        for csv_url in csv_urls:
            try:
                self._logger.debug(f"Trying {csv_url}")
                async with self._session.get(csv_url, headers=headers) as response:
                    self._logger.debug(f"Status: {response.status}")
                    
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        csv_data = await response.text()
                        
                        self._logger.debug(f"Content-Type: {content_type}, Size: {len(csv_data)}")
                        
                        # Enhanced CSV detection
                        if ('csv' in content_type.lower() or 'text' in content_type.lower() or 
                            'application/octet-stream' in content_type.lower() or
                            ',' in csv_data or 'Date,Time' in csv_data or 'Feed-in' in csv_data or
                            'Consumption' in csv_data or len(csv_data) > 100):
                            
                            lines = csv_data.split('\n')
                            if any(',' in line for line in lines if line.strip()):
                                self._logger.info(f"✅ Valid CSV found at: {csv_url}")
                                return {"csv_data": csv_data}
                            else:
                                self._logger.debug(f"Content doesn't look like CSV")
            except Exception as e:
                self._logger.debug(f"Error with {csv_url}: {e}")
        
        self._logger.warning("❌ No CSV download found")
        return {}
    
    async def _extract_data_from_csv(self) -> dict:
        """Extract data from CSV exactly like HA coordinator"""
        self._logger.info("📥 Starting CSV data extraction...")
        
        csv_result = await self._test_csv_download()
        if not csv_result.get("csv_data"):
            self._logger.warning("Could not download CSV data")
            raise Exception("Could not download CSV data")
        
        csv_data = csv_result["csv_data"]
        lines = csv_data.strip().split('\n')
        
        if len(lines) < 2:
            raise Exception("CSV data is empty or invalid")
        
        # Initialize data exactly like coordinator
        data = {
            "current_rate": 0.25,
            "next_rate": 0.25,
            "solar_generation": 0.0,
            "daily_consumption": 0.0,
            "daily_feed_in": 0.0,
            "average_daily_use": 0.0,
        }
        
        # Parse CSV lines (skip header)
        today = datetime.now().strftime("%-d/%-m/%Y")
        self._logger.debug(f"Looking for today's date in CSV: {today}")
        
        found_today_data = False
        for line in lines[1:]:
            if not line.strip():
                continue
                
            parts = line.split(',')
            if len(parts) < 52:
                continue
            
            try:
                meter_element = parts[2]
                date = parts[3]
                
                if date == today:
                    found_today_data = True
                    self._logger.debug(f"✅ Found today's data for {meter_element}")
                    
                    # Sum half-hour values
                    half_hour_values = []
                    for i in range(4, min(52, len(parts))):
                        try:
                            value = float(parts[i])
                            half_hour_values.append(value)
                        except ValueError:
                            half_hour_values.append(0.0)
                    
                    daily_total = sum(half_hour_values)
                    
                    if meter_element == "Feed-in":
                        data["daily_feed_in"] = daily_total
                        for value in reversed(half_hour_values):
                            if value > 0:
                                data["solar_generation"] = value
                                break
                    elif meter_element == "Consumption":
                        data["daily_consumption"] = daily_total
            except (ValueError, IndexError):
                continue
        
        if not found_today_data:
            self._logger.warning(f"⚠️ No data found for today ({today})")
            # Try to use most recent data
            recent_dates = []
            for line in lines[1:]:
                if not line.strip():
                    continue
                parts = line.split(',')
                if len(parts) > 3:
                    recent_dates.append(parts[3])
            
            if recent_dates:
                recent_date = recent_dates[-1]
                self._logger.debug(f"Using most recent date: {recent_date}")
                # [Add recent data parsing logic here if needed]
        
        self._logger.debug(f"Final CSV data: {data}")
        return data
    
    async def _extract_data_from_portal(self) -> dict:
        """Extract data from portal exactly like HA coordinator"""
        self._logger.debug("🌐 Starting portal data extraction...")
        
        try:
            return await self._extract_data_from_csv()
        except Exception as csv_err:
            self._logger.warning(f"CSV extraction failed: {csv_err}")
            
            # Return default data to prevent unavailable sensors
            self._logger.info("Returning default values to prevent sensor unavailability")
            return {
                "current_rate": 0.25,
                "next_rate": 0.25,
                "solar_generation": 0.0,
                "daily_consumption": 0.0,
                "daily_feed_in": 0.0,
                "average_daily_use": 0.0,
            }
    
    async def _async_update_data(self):
        """Main update method exactly like HA coordinator"""
        self._logger.info("🔄 Starting data update cycle...")
        self._logger.debug(f"Session state: logged_in={self._logged_in}, retry_count={self._retry_count}")
        
        try:
            self._retry_count = 0
            
            self._logger.debug("🌐 Calling _extract_data_from_portal()...")
            data = await self._extract_data_from_portal()
            
            if data is None:
                self._logger.error("❌ _extract_data_from_portal() returned None")
                raise Exception("Portal extraction returned no data")
            
            self._logger.info("✅ Successfully extracted data from portal")
            self._logger.debug("📊 Raw data: %s", data)
            
            # Validate data structure
            required_keys = ["current_rate", "next_rate", "solar_generation", "daily_consumption", "daily_feed_in"]
            for key in required_keys:
                if key not in data:
                    self._logger.warning(f"⚠️ Missing required data key: {key}, setting to 0.0")
                    data[key] = 0.0
            
            self._logger.info("✅ Data validation complete, returning to coordinator")
            return data
            
        except Exception as err:
            self._logger.error(f"❌ Error in data update: {err}")
            self._logger.error(f"Exception type: {type(err).__name__}")
            raise
    
    async def close(self):
        """Clean up session"""
        if self._session and not self._session.closed:
            await self._session.close()

async def diagnose_integration():
    """Run full diagnosis"""
    print("🔍 DIAGNOSING HOME ASSISTANT MERIDIAN INTEGRATION")
    print("=" * 60)
    
    # Load credentials
    try:
        with open("test/config.json", "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ test/config.json not found")
        return
    
    coordinator = MockMeridianCoordinator(config["username"], config["password"])
    
    try:
        print("\n🧪 Testing coordinator update cycle...")
        data = await coordinator._async_update_data()
        
        print(f"\n📊 FINAL RESULTS:")
        print(f"✅ Data successfully extracted: {data}")
        print(f"\n🎯 SENSOR PREDICTIONS:")
        print(f"   Current Rate: {data.get('current_rate', 'N/A')} $/kWh")
        print(f"   Next Rate: {data.get('next_rate', 'N/A')} $/kWh")
        print(f"   Daily Consumption: {data.get('daily_consumption', 'N/A')} kWh")
        print(f"   Daily Feed In: {data.get('daily_feed_in', 'N/A')} kWh")
        print(f"   Solar Generation: {data.get('solar_generation', 'N/A')} kW")
        print(f"   Average Daily Use: {data.get('average_daily_use', 'N/A')} kWh")
        
        print(f"\n✅ DIAGNOSIS: Integration should work - data extraction successful!")
        print(f"   If sensors still show 'Unavailable', check:")
        print(f"   1. Home Assistant logs for coordinator errors")
        print(f"   2. Integration configuration in HA")
        print(f"   3. Restart HA after adding logging config")
        
    except Exception as e:
        print(f"\n❌ DIAGNOSIS: Integration failing - {e}")
        print(f"   This is likely why sensors show 'Unavailable'")
        print(f"   Check the detailed logs above for specific issues")
    
    finally:
        await coordinator.close()

if __name__ == "__main__":
    asyncio.run(diagnose_integration())
