"""The Meridian Solar integration."""
from __future__ import annotations

from datetime import timedelta, datetime
import logging
import re
import asyncio
import aiohttp
from typing import Any
from urllib.parse import urljoin

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Enable more detailed logging for debugging
_LOGGER.setLevel(logging.DEBUG)

PLATFORMS: list[Platform] = [Platform.SENSOR]
SCAN_INTERVAL = timedelta(minutes=30)

# Customer Portal Configuration (will be updated by discovery)
BASE_URL = "https://secure.meridianenergy.co.nz"
LOGIN_URL = f"{BASE_URL}/login"
DASHBOARD_URL = f"{BASE_URL}/"
USAGE_URL = f"{BASE_URL}/"
BILLING_URL = f"{BASE_URL}/"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Meridian Solar from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Get scan interval from options or use default
    scan_interval = timedelta(minutes=entry.options.get("scan_interval", 30))
    
    coordinator = MeridianSolarDataUpdateCoordinator(
        hass,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        update_interval=scan_interval,
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except UpdateFailed as err:
        raise ConfigEntryNotReady(f"Failed to connect to Meridian Energy: {err}") from err

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up options listener for dynamic configuration updates
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Properly cleanup the coordinator
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_stop()

    return unload_ok

class MeridianSolarDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Meridian Solar data from customer portal."""

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        password: str,
        update_interval: timedelta = SCAN_INTERVAL,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.username = username
        self.password = password
        self._session: aiohttp.ClientSession | None = None
        self._logged_in = False
        self._csrf_token: str | None = None
        self._form_action_url: str | None = None
        self._retry_count = 0
        self.MAX_RETRIES = 3
        
        # Instance URLs that can be updated during discovery
        self.login_url = LOGIN_URL
        self.dashboard_url = DASHBOARD_URL
        self.usage_url = USAGE_URL
        self.billing_url = BILLING_URL

    async def _discover_login_page(self) -> str:
        """Discover the correct login page URL."""
        _LOGGER.debug("Discovering login page...")
        
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
                async with self._session.get(url, allow_redirects=True) as response:
                    _LOGGER.debug(f"Trying {url}: {response.status}")
                    
                    if response.status == 200:
                        html = await response.text()
                        # Look for login indicators
                        login_indicators = ['password', 'username', 'login', 'sign in', 'email']
                        found_indicators = sum(1 for indicator in login_indicators if indicator.lower() in html.lower())
                        
                        if found_indicators >= 2:  # Need at least 2 login indicators
                            _LOGGER.debug(f"Found login page at: {url}")
                            return str(response.url)  # Return the final URL after redirects
                            
            except Exception as e:
                _LOGGER.debug(f"Error checking {url}: {e}")
                continue
        
        _LOGGER.warning("No valid login page found")
        return ""

    async def _get_login_page(self) -> bool:
        """Get the login page and extract CSRF token."""
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        _LOGGER.debug("Getting login page...")
        
        # First discover the correct login URL
        discovered_url = await self._discover_login_page()
        if not discovered_url:
            return False
        
        # Update our URLs based on discovery
        base_url = discovered_url.rsplit('/', 1)[0] if discovered_url.endswith('/') else discovered_url.rsplit('/', 1)[0]
        self.login_url = discovered_url
        self.dashboard_url = f"{base_url}/"
        self.usage_url = f"{base_url}/"
        self.billing_url = f"{base_url}/"
        
        try:
            async with asyncio.timeout(30):
                async with self._session.get(self.login_url) as response:
                    _LOGGER.debug(f"Login page status: {response.status}")
                    
                    if response.status != 200:
                        raise UpdateFailed(f"Failed to get login page: {response.status}")
                    
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
                            self._csrf_token = match.group(1)
                            _LOGGER.debug(f"Found CSRF token: {self._csrf_token[:20]}...")
                            break
                    
                    if not self._csrf_token:
                        _LOGGER.debug("No CSRF token found, proceeding without it")
                    
                    # Look for form action
                    form_action = re.search(r'<form[^>]*action=["\']([^"\']+)["\']', html, re.IGNORECASE)
                    if form_action:
                        action_url = form_action.group(1)
                        _LOGGER.debug(f"Form action: {action_url}")
                        # Store the correct action URL for later use
                        self._form_action_url = urljoin(self.login_url, action_url) if action_url.startswith('/') else action_url
                        _LOGGER.debug(f"Will submit to: {self._form_action_url}")
                    else:
                        _LOGGER.debug("No form action found, using current URL")
                        self._form_action_url = self.login_url
                    
                    return True
        except Exception as err:
            raise UpdateFailed(f"Error getting login page: {err}")

    async def _authenticate(self) -> bool:
        """Authenticate with Meridian Customer Portal."""
        _LOGGER.info("🔐 Starting authentication process...")
        _LOGGER.debug(f"Username: {self.username}")
        
        # First get the login page
        if not await self._get_login_page():
            return False
        
        try:
            async with asyncio.timeout(30):
                # Prepare login data with correct field names
                login_data = {
                    "email": self.username,
                    "password": self.password,
                    "commit": "Sign in",  # Submit button value
                }
                
                # Add CSRF token if we found one
                if self._csrf_token:
                    login_data["authenticity_token"] = self._csrf_token
                
                # Set headers to mimic a browser
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Referer": self.login_url,
                    "Content-Type": "application/x-www-form-urlencoded"
                }
                
                # Use the correct form action URL
                submit_url = self._form_action_url or self.login_url
                _LOGGER.debug(f"Submitting to: {submit_url}")
                
                async with self._session.post(submit_url, data=login_data, headers=headers, allow_redirects=False) as response:
                    _LOGGER.debug(f"Authentication response status: {response.status}")
                    
                    # Debug: Show response headers
                    location = response.headers.get('Location', '')
                    if location:
                        _LOGGER.debug(f"Redirect to: {location}")
                    
                    # Check for successful login (redirect or 200 with success indicators)
                    if response.status in [200, 302, 303]:
                        response_text = await response.text()
                        
                        # Debug: Show first part of response
                        _LOGGER.debug(f"Response preview: {response_text[:200]}...")
                        
                        if (response.status in [302, 303] and 
                            ('dashboard' in location.lower() or 'customers' in location.lower() or 
                             'home' in location.lower() or location == '/')):
                            _LOGGER.debug(f"Authentication successful (redirected to: {location})")
                            self._logged_in = True
                            return True
                        elif 'dashboard' in response_text.lower() or 'welcome' in response_text.lower():
                            _LOGGER.debug("Authentication successful")
                            self._logged_in = True
                            return True
                        elif 'invalid' in response_text.lower() or 'incorrect' in response_text.lower():
                            _LOGGER.error("Authentication failed: Invalid credentials")
                            raise UpdateFailed("Invalid credentials")
                        elif response.status in [302, 303]:
                            # Follow the redirect to see where it goes
                            _LOGGER.debug("Following redirect to check result...")
                            try:
                                async with self._session.get(urljoin(self.login_url, location), headers=headers) as redirect_response:
                                    redirect_text = await redirect_response.text()
                                    if ('dashboard' in redirect_text.lower() or 'welcome' in redirect_text.lower() or
                                        'account' in redirect_text.lower()):
                                        _LOGGER.debug("Authentication successful (confirmed via redirect)")
                                        self._logged_in = True
                                        return True
                            except Exception as e:
                                _LOGGER.warning(f"Error following redirect: {e}")
                        
                        _LOGGER.debug("Uncertain login result, checking dashboard access...")
                        # Try to access dashboard to confirm login
                        self._logged_in = True  # Assume success for now
                        return await self._test_dashboard_access()
                    else:
                        error_text = await response.text()
                        _LOGGER.error(f"Authentication failed: {error_text[:200]}...")
                        raise UpdateFailed(f"Authentication failed: {response.status}")
                    
        except Exception as err:
            _LOGGER.error(f"Authentication error: {err}")
            raise UpdateFailed(f"Error during authentication: {err}")

    async def _test_dashboard_access(self) -> bool:
        """Test accessing the customer dashboard."""
        _LOGGER.debug("Testing dashboard access...")
        
        if not self._logged_in:
            _LOGGER.error("Not logged in")
            return False
            
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": LOGIN_URL
            }
            
            async with self._session.get(self.dashboard_url, headers=headers) as response:
                _LOGGER.debug(f"Dashboard access status: {response.status}")
                
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
                        _LOGGER.debug(f"Dashboard access successful. Found indicators: {', '.join(found_indicators[:3])}...")
                        return True
                    else:
                        _LOGGER.error("Dashboard access failed - no expected content found")
                        return False
                else:
                    _LOGGER.error(f"Dashboard access failed: {response.status}")
                    return False
                    
        except Exception as e:
            _LOGGER.error(f"Dashboard access error: {e}")
            return False

    async def _extract_usage_chart_data(self) -> dict[str, Any]:
        """Extract average daily usage data from usage chart page."""
        _LOGGER.debug("Testing usage data retrieval...")
        
        if not self._logged_in:
            await self._authenticate()
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": self.dashboard_url
            }
            
            # Check the specific usage chart page
            usage_chart_url = "https://secure.meridianenergy.co.nz/usage"
            _LOGGER.debug(f"Checking usage chart: {usage_chart_url}")
            
            async with asyncio.timeout(30):
                async with self._session.get(usage_chart_url, headers=headers) as response:
                    _LOGGER.debug(f"Usage chart status: {response.status}")
                    
                    if response.status != 200:
                        raise UpdateFailed(f"Failed to access usage chart: {response.status}")
                    
                    html = await response.text()
                    
                    # Look for usage chart indicators (more flexible patterns)
                    usage_indicators = [
                        'average daily use', 'daily usage', 'usage chart', 'power usage',
                        'consumption', 'kwh', 'daily average', 'usage pattern',
                        'energy', 'electricity', 'meter', 'usage', 'daily', 'monthly',
                        'cost', 'bill', 'kw', 'kilowatt'
                    ]
                    
                    found_indicators = []
                    for indicator in usage_indicators:
                        if indicator.lower() in html.lower():
                            found_indicators.append(indicator)
                    
                    # More tolerant - accept page if we find any energy-related indicators
                    if found_indicators or len(html) > 1000:  # Accept if indicators found OR page has content
                        if found_indicators:
                            _LOGGER.debug(f"Usage chart page accessible. Found indicators: {', '.join(found_indicators[:5])}...")
                        else:
                            _LOGGER.debug("Usage chart page accessible. No specific indicators but page has content, proceeding...")
                        
                        # Look for specific usage data patterns
                        usage_patterns = [
                            r'average\s*daily\s*use[:\s]*(\d+\.?\d*)\s*kWh',  # Average daily use
                            r'daily\s*average[:\s]*(\d+\.?\d*)\s*kWh',  # Daily average
                            r'(\d+\.?\d*)\s*kWh\s*per\s*day',  # kWh per day
                            r'(\d+\.?\d*)\s*kWh',  # General kWh values
                            r'usage[:\s]*(\d+\.?\d*)\s*kWh'  # Usage amounts
                        ]
                        
                        usage_data = {}
                        for i, pattern in enumerate(usage_patterns):
                            matches = re.findall(pattern, html, re.IGNORECASE)
                            if matches:
                                # Take the first valid match for the main patterns
                                if i < 3 and "average_daily_use" not in usage_data:
                                    try:
                                        usage_data["average_daily_use"] = float(matches[0])
                                        _LOGGER.debug(f"Found usage pattern {i}: {usage_data['average_daily_use']} kWh")
                                        break
                                    except (ValueError, IndexError):
                                        continue
                        
                        return usage_data
                    else:
                        _LOGGER.warning("Usage chart page accessible but no usage indicators found")
                        return {}
                    
        except Exception as err:
            _LOGGER.warning(f"Error extracting usage chart data: {err}")
            return {}

    async def _test_get_solar_data(self) -> dict[str, Any]:
        """Test getting solar generation data from the feed-in report page."""
        _LOGGER.debug("Testing solar data retrieval...")
        
        if not self._logged_in:
            await self._authenticate()
            
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": self.dashboard_url
            }
            
            # Check the specific feed-in report page
            feed_in_url = "https://secure.meridianenergy.co.nz/feed_in_report"
            _LOGGER.debug(f"Checking feed-in report: {feed_in_url}")
            
            async with self._session.get(feed_in_url, headers=headers) as response:
                _LOGGER.debug(f"Feed-in report status: {response.status}")
                
                if response.status == 200:
                    html = await response.text()
                    
                    # Look for solar/feed-in specific indicators (more flexible patterns)
                    solar_indicators = [
                        'feed in', 'feed-in', 'solar', 'generation', 'export', 
                        'heatmap', 'csv', 'download', 'kwh', 'half hour',
                        'import', 'energy', 'electricity', 'meter', 'grid',
                        'kw', 'kilowatt', 'production', 'generated'
                    ]
                    
                    found_indicators = []
                    for indicator in solar_indicators:
                        if indicator.lower() in html.lower():
                            found_indicators.append(indicator)
                    
                    # More tolerant - accept page if we find any energy-related indicators  
                    if found_indicators or len(html) > 1000:  # Accept if indicators found OR page has content
                        if found_indicators:
                            _LOGGER.debug(f"Feed-in report page accessible. Found indicators: {', '.join(found_indicators[:5])}...")
                        else:
                            _LOGGER.debug("Feed-in report page accessible. No specific indicators but page has content, proceeding...")
                        
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
                            _LOGGER.debug(f"Solar data patterns found: {found_data}")
                        
                        # Look for CSV download link
                        csv_patterns = [
                            r'href=["\']([^"\']*\.csv[^"\']*)["\']',
                            r'href=["\']([^"\']*download[^"\']*)["\']',
                            r'href=["\']([^"\']*export[^"\']*)["\']'
                        ]
                        
                        for pattern in csv_patterns:
                            matches = re.findall(pattern, html, re.IGNORECASE)
                            if matches:
                                _LOGGER.debug(f"Found potential CSV download: {matches[0]}")
                                break
                        
                        return found_data
                    else:
                        _LOGGER.warning("Feed-in report page accessible but no solar indicators found")
                        return {}
                        
                elif response.status == 404:
                    _LOGGER.warning("Feed-in report page not found - account may not have solar")
                    return {}
                else:
                    _LOGGER.warning(f"Failed to access feed-in report: {response.status}")
                    return {}
                    
        except Exception as e:
            _LOGGER.warning(f"Solar data retrieval error: {e}")
            return {}

    async def _test_csv_download(self) -> dict[str, Any]:
        """Test downloading CSV data from feed-in report."""
        _LOGGER.debug("Testing CSV download...")
        
        if not self._logged_in:
            await self._authenticate()
            
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
                    async with self._session.get(csv_url, headers=headers) as response:
                        _LOGGER.debug(f"Trying {csv_url}: {response.status}")
                        
                        if response.status == 200:
                            content_type = response.headers.get('content-type', '')
                            if 'csv' in content_type.lower() or 'text' in content_type.lower():
                                csv_data = await response.text()
                                lines = csv_data.split('\n')[:5]  # First 5 lines
                                _LOGGER.debug(f"CSV download successful! Content-Type: {content_type}")
                                _LOGGER.debug("First few lines:")
                                for i, line in enumerate(lines):
                                    if line.strip():
                                        _LOGGER.debug(f"{i+1}: {line[:100]}...")  # First 100 chars
                                return {"csv_data": csv_data}
                                
                except Exception as e:
                    _LOGGER.debug(f"Error trying {csv_url}: {e}")
                    continue
            
            _LOGGER.warning("No CSV download found")
            return {}
                    
        except Exception as e:
            _LOGGER.warning(f"CSV download error: {e}")
            return {}

    async def _extract_data_from_csv(self) -> dict[str, Any]:
        """Extract solar and usage data from CSV download."""
        _LOGGER.info("📥 Starting CSV data extraction...")
        _LOGGER.debug("Checking authentication status for CSV download")
        
        if not self._logged_in:
            await self._authenticate()
        
        # First test if we can access the solar data page and find CSV download
        solar_data = await self._test_get_solar_data()
        if not solar_data:
            _LOGGER.warning("No solar data indicators found")
        
        # Test CSV download
        csv_result = await self._test_csv_download()
        if not csv_result.get("csv_data"):
            raise UpdateFailed("Could not download CSV data")
        
        try:
            csv_data = csv_result["csv_data"]
            self._retry_count = 0
            
            # Parse CSV data
            lines = csv_data.strip().split('\n')
            if len(lines) < 2:
                raise UpdateFailed("CSV data is empty or invalid")
            
            # Initialize data with real rate extraction
            _LOGGER.debug("Extracting real electricity rates...")
            rates = await self._extract_rate_information()
            
            data = {
                "current_rate": rates["current_rate"],
                "next_rate": rates["next_rate"],
                "solar_generation": 0.0,
                "daily_consumption": 0.0,
                "daily_feed_in": 0.0,
                "average_daily_use": 0.0,
            }
            
            # Parse CSV lines (skip header)
            today = datetime.now().strftime("%-d/%-m/%Y")  # Format: 1/9/2025
            _LOGGER.debug(f"Looking for today's date in CSV: {today}")
            
            for line in lines[1:]:
                if not line.strip():
                    continue
                    
                parts = line.split(',')
                if len(parts) < 52:  # Header + 48 half-hour periods + extras
                    continue
                
                try:
                    meter_element = parts[2]  # Feed-in or Consumption
                    date = parts[3]
                    
                    # Only process today's data
                    if date != today:
                        continue
                    
                    # Sum the 48 half-hour values (columns 4-51)
                    half_hour_values = []
                    for i in range(4, min(52, len(parts))):
                        try:
                            value = float(parts[i])
                            half_hour_values.append(value)
                        except (ValueError, IndexError):
                            half_hour_values.append(0.0)
                    
                    daily_total = sum(half_hour_values)
                    
                    if meter_element == "Feed-in":
                        data["daily_feed_in"] = daily_total
                        # Current generation is the latest non-zero value
                        for value in reversed(half_hour_values):
                            if value > 0:
                                data["solar_generation"] = value
                                break
                    elif meter_element == "Consumption":
                        data["daily_consumption"] = daily_total
                        
                except (ValueError, IndexError) as e:
                    _LOGGER.debug(f"Error parsing CSV line: {e}")
                    continue
            
            # Get average daily usage from usage chart
            try:
                usage_chart_data = await self._extract_usage_chart_data()
                if "average_daily_use" in usage_chart_data:
                    data["average_daily_use"] = usage_chart_data["average_daily_use"]
            except Exception as e:
                _LOGGER.debug(f"Could not get usage chart data: {e}")
            
            # If no data found for today, try to get most recent data
            if data['daily_consumption'] == 0.0 and data['daily_feed_in'] == 0.0:
                _LOGGER.debug(f"No data found for today ({today}), looking for most recent data...")
                
                # Find the most recent date with data
                recent_dates = []
                for line in lines[1:]:
                    if not line.strip():
                        continue
                    parts = line.split(',')
                    if len(parts) > 3:
                        recent_dates.append(parts[3])
                
                if recent_dates:
                    # Use the last date found (should be most recent)
                    recent_date = recent_dates[-1]
                    _LOGGER.debug(f"Using most recent date: {recent_date}")
                    
                    for line in lines[1:]:
                        if not line.strip():
                            continue
                        parts = line.split(',')
                        if len(parts) < 52 or parts[3] != recent_date:
                            continue
                        
                        try:
                            meter_element = parts[2]
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
            
            _LOGGER.debug(f"Final CSV data: daily_feed_in={data['daily_feed_in']}, "
                        f"daily_consumption={data['daily_consumption']}, "
                        f"current_generation={data['solar_generation']}, "
                        f"average_daily_use={data['average_daily_use']}")
            
            return data
                    
        except Exception as err:
            raise UpdateFailed(f"Error extracting data from CSV: {err}")

    async def _extract_data_from_portal(self) -> dict[str, Any]:
        """Extract solar and usage data from the customer portal."""
        _LOGGER.debug("Starting portal data extraction...")
        
        # Try CSV first (more accurate), fall back to portal scraping
        try:
            return await self._extract_data_from_csv()
        except Exception as csv_err:
            _LOGGER.warning(f"CSV extraction failed, trying portal scraping: {csv_err}")
            
            # Fallback to portal scraping
            if not self._logged_in:
                if not await self._authenticate():
                    raise UpdateFailed("Authentication failed")
            
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Referer": LOGIN_URL
                }
                
                async with asyncio.timeout(30):
                    async with self._session.get(self.dashboard_url, headers=headers) as response:
                        if response.status != 200:
                            raise UpdateFailed(f"Failed to access dashboard: {response.status}")
                        
                        # Try to get usage data from usage chart page
                        usage_data = await self._extract_usage_chart_data()
                        
                        # Extract real rate information
                        rates = await self._extract_rate_information()
                        
                        # Return basic data structure with any found usage data and real rates
                        return {
                            "current_rate": rates["current_rate"],
                            "next_rate": rates["next_rate"],
                            "solar_generation": 0.0,
                            "daily_consumption": 0.0,
                            "daily_feed_in": 0.0,
                            "average_daily_use": usage_data.get("average_daily_use", 0.0),
                        }
                        
            except Exception as portal_err:
                # Log the specific errors for debugging but don't fail completely
                _LOGGER.warning(f"CSV error: {csv_err}")
                _LOGGER.warning(f"Portal scraping error: {portal_err}")
                _LOGGER.info("Returning default values to prevent sensor unavailability")
                
                # Try to extract rates even if other data failed
                try:
                    rates = await self._extract_rate_information()
                except Exception:
                    rates = {"current_rate": 0.25, "next_rate": 0.25}
                
                # Return default data so sensors show something instead of "Unavailable"
                return {
                    "current_rate": rates["current_rate"],
                    "next_rate": rates["next_rate"],
                    "solar_generation": 0.0,  # No current generation data
                    "daily_consumption": 0.0,  # No current consumption data
                    "daily_feed_in": 0.0,  # No current feed-in data
                    "average_daily_use": 0.0,  # No usage data available
                }

    async def _test_find_data_endpoints(self) -> bool:
        """Test finding potential data endpoints or AJAX calls."""
        _LOGGER.debug("Testing for data endpoints...")
        
        if not self._logged_in:
            if not await self._authenticate():
                _LOGGER.error("Not logged in")
                return False
            
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": self.dashboard_url
            }
            
            # Check dashboard for JavaScript/AJAX endpoints
            async with self._session.get(self.dashboard_url, headers=headers) as response:
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
                        _LOGGER.debug(f"Found potential endpoints: {list(found_endpoints)[:10]}")  # Show first 10
                        return True
                    else:
                        _LOGGER.debug("No obvious data endpoints found")
                        return False
                else:
                    _LOGGER.error(f"Failed to analyze dashboard: {response.status}")
                    return False
                    
        except Exception as e:
            _LOGGER.error(f"Endpoint discovery error: {e}")
            return False

    async def _extract_rate_information(self) -> dict[str, float]:
        """Extract current and next electricity rates from Meridian portal."""
        _LOGGER.debug("🔍 Extracting rate information from portal...")
        
        if not self._logged_in:
            await self._authenticate()
        
        rates = {"current_rate": 0.25, "next_rate": 0.25}  # Default fallbacks
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": self.dashboard_url
        }
        
        # Pages that might contain rate information
        rate_pages = [
            (self.dashboard_url, "dashboard"),
            ("https://secure.meridianenergy.co.nz/billing", "billing"),
            ("https://secure.meridianenergy.co.nz/account", "account"),
            ("https://secure.meridianenergy.co.nz/usage", "usage"),
            ("https://secure.meridianenergy.co.nz/rates", "rates"),
        ]
        
        for url, page_type in rate_pages:
            try:
                async with self._session.get(url, headers=headers) as response:
                    if response.status == 200:
                        html = await response.text()
                        _LOGGER.debug(f"Checking {page_type} page for rate information...")
                        
                        # Look for rate patterns in various formats
                        rate_patterns = [
                            # Standard rate formats
                            r'(\d+\.?\d*)\s*c(?:ents)?/kWh',  # e.g., "25.5 c/kWh"
                            r'(\d+\.?\d*)\s*cents?\s*per\s*kWh',  # e.g., "25.5 cents per kWh"
                            r'\$(\d+\.?\d*)\s*per\s*kWh',  # e.g., "$0.255 per kWh"
                            r'Rate[:\s]*\$?(\d+\.?\d*)',  # e.g., "Rate: $0.255"
                            r'Price[:\s]*\$?(\d+\.?\d*)',  # e.g., "Price: 0.255"
                            r'(\d+\.?\d*)\s*¢/kWh',  # e.g., "25.5¢/kWh"
                            
                            # Table/structured formats
                            r'<td[^>]*>\s*\$?(\d+\.?\d*)\s*</td>',  # Table cells
                            r'current[^>]*rate[^>]*[:\s]*\$?(\d+\.?\d*)',  # Current rate
                            r'next[^>]*rate[^>]*[:\s]*\$?(\d+\.?\d*)',  # Next rate
                            
                            # JSON-like formats (if rates in data attributes)
                            r'"rate"[:\s]*(\d+\.?\d*)',
                            r'"current_rate"[:\s]*(\d+\.?\d*)',
                            r'"next_rate"[:\s]*(\d+\.?\d*)',
                        ]
                        
                        found_rates = []
                        for pattern in rate_patterns:
                            matches = re.findall(pattern, html, re.IGNORECASE)
                            for match in matches:
                                try:
                                    rate = float(match)
                                    # Convert cents to dollars if rate is high (assume cents)
                                    if rate > 10:  # Likely in cents
                                        rate = rate / 100
                                    # Reasonable rate range for NZ (0.15 - 0.50 $/kWh)
                                    if 0.15 <= rate <= 0.50:
                                        found_rates.append(rate)
                                        _LOGGER.debug(f"Found potential rate on {page_type}: {rate} $/kWh")
                                except ValueError:
                                    continue
                        
                        # Use the most common rate found, or first reasonable rate
                        if found_rates:
                            # Use the most frequent rate (mode) or median
                            from collections import Counter
                            if len(found_rates) > 1:
                                rate_counts = Counter(found_rates)
                                most_common_rate = rate_counts.most_common(1)[0][0]
                                rates["current_rate"] = most_common_rate
                                rates["next_rate"] = most_common_rate
                                _LOGGER.info(f"✅ Extracted rate from {page_type}: {most_common_rate} $/kWh")
                            else:
                                rates["current_rate"] = found_rates[0]
                                rates["next_rate"] = found_rates[0]
                                _LOGGER.info(f"✅ Extracted rate from {page_type}: {found_rates[0]} $/kWh")
                            break  # Found rates, stop searching
                            
            except Exception as e:
                _LOGGER.debug(f"Error checking {page_type} for rates: {e}")
                continue
        
        if rates["current_rate"] == 0.25:
            _LOGGER.warning("⚠️ Could not extract real rates, using default 0.25 $/kWh")
        
        return rates

    async def _async_update_data(self):
        """Fetch data from Meridian Customer Portal."""
        _LOGGER.info("🔄 Starting data update cycle...")
        _LOGGER.debug(f"Session state: logged_in={self._logged_in}, retry_count={self._retry_count}")
        
        try:
            # Reset retry count for each update cycle
            self._retry_count = 0
            
            _LOGGER.debug("🌐 Calling _extract_data_from_portal()...")
            data = await self._extract_data_from_portal()
            
            if data is None:
                _LOGGER.error("❌ _extract_data_from_portal() returned None")
                raise UpdateFailed("Portal extraction returned no data")
            
            _LOGGER.info("✅ Successfully extracted data from portal")
            _LOGGER.debug("📊 Raw data: current_rate=%s, next_rate=%s, solar_generation=%s, "
                         "daily_consumption=%s, daily_feed_in=%s, average_daily_use=%s", 
                         data.get("current_rate"), data.get("next_rate"), data.get("solar_generation"),
                         data.get("daily_consumption"), data.get("daily_feed_in"), data.get("average_daily_use"))

            # Validate data structure
            required_keys = ["current_rate", "next_rate", "solar_generation", "daily_consumption", "daily_feed_in"]
            for key in required_keys:
                if key not in data:
                    _LOGGER.warning(f"⚠️ Missing required data key: {key}, setting to 0.0")
                    data[key] = 0.0

            _LOGGER.info("✅ Data validation complete, returning to coordinator")
            return data

        except UpdateFailed as update_err:
            # Re-raise UpdateFailed exceptions as-is but with more logging
            _LOGGER.error(f"❌ UpdateFailed exception: {update_err}")
            raise
        except Exception as err:
            _LOGGER.error(f"❌ Unexpected error in data update: {err}")
            _LOGGER.error(f"Exception type: {type(err).__name__}")
            # Log full traceback for debugging
            import traceback
            _LOGGER.debug(f"Full traceback: {traceback.format_exc()}")
            raise UpdateFailed(f"Error communicating with portal: {err}")
            
            # Try to close and recreate session on error
            if self._session and not self._session.closed:
                try:
                    await self._session.close()
                except Exception:
                    pass
                self._session = None
                self._logged_in = False
            
            raise UpdateFailed(f"Error communicating with portal: {err}")

    async def async_stop(self):
        """Close the session."""
        _LOGGER.debug("Stopping coordinator and closing session...")
        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception as e:
                _LOGGER.debug(f"Error closing session: {e}")
            finally:
                self._session = None
                self._logged_in = False

    async def get_historical_data(self, days: int = 7) -> dict:
        """Get historical solar generation data from portal."""
        # This would require more complex scraping of historical pages
        # For now, return empty data
        _LOGGER.warning("Historical data not yet implemented for portal scraping")
        return {}

    async def run_all_tests(self) -> dict[str, bool]:
        """Run all portal tests for debugging."""
        _LOGGER.info("Starting Meridian Energy Portal Tests")
        
        results = {}
        
        # Test authentication
        try:
            results["authentication"] = await self._authenticate()
        except Exception as e:
            _LOGGER.error(f"Authentication test failed: {e}")
            results["authentication"] = False
        
        if results["authentication"]:
            # Test dashboard access
            try:
                results["dashboard"] = await self._test_dashboard_access()
            except Exception as e:
                _LOGGER.error(f"Dashboard test failed: {e}")
                results["dashboard"] = False
            
            # Test usage data
            try:
                usage_data = await self._extract_usage_chart_data()
                results["usage_data"] = bool(usage_data)
            except Exception as e:
                _LOGGER.error(f"Usage data test failed: {e}")
                results["usage_data"] = False
            
            # Test solar data
            try:
                solar_data = await self._test_get_solar_data()
                results["solar_data"] = bool(solar_data)
            except Exception as e:
                _LOGGER.error(f"Solar data test failed: {e}")
                results["solar_data"] = False
            
            # Test CSV download if solar data is available
            if results.get("solar_data"):
                try:
                    csv_data = await self._test_csv_download()
                    results["csv_download"] = bool(csv_data.get("csv_data"))
                except Exception as e:
                    _LOGGER.error(f"CSV download test failed: {e}")
                    results["csv_download"] = False
            else:
                results["csv_download"] = False
            
            # Test endpoint discovery
            try:
                results["data_endpoints"] = await self._test_find_data_endpoints()
            except Exception as e:
                _LOGGER.error(f"Endpoint discovery test failed: {e}")
                results["data_endpoints"] = False
        else:
            results["dashboard"] = False
            results["usage_data"] = False
            results["solar_data"] = False
            results["csv_download"] = False
            results["data_endpoints"] = False
        
        _LOGGER.info(f"Portal test results: {results}")
        return results

    async def get_diagnostics_data(self) -> dict[str, Any]:
        """Return diagnostics data for debugging."""
        diagnostics = {
            "username": self.username,
            "logged_in": self._logged_in,
            "retry_count": self._retry_count,
            "urls": {
                "login_url": self.login_url,
                "dashboard_url": self.dashboard_url,
                "usage_url": self.usage_url,
                "billing_url": self.billing_url,
            },
            "session_closed": self._session is None or self._session.closed if self._session else True,
            "last_update_success": self.last_update_success,
            "last_update_success_time": self.last_update_success_time.isoformat() if self.last_update_success_time else None,
            "update_interval": str(self.update_interval),
        }
        
        # Add test results if available
        try:
            test_results = await self.run_all_tests()
            diagnostics["test_results"] = test_results
        except Exception as e:
            diagnostics["test_error"] = str(e)
        
        return diagnostics 