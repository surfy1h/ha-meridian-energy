"""The Meridian Solar integration."""
from __future__ import annotations

from datetime import timedelta, datetime
import logging
import json
import aiohttp
import async_timeout
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]
SCAN_INTERVAL = timedelta(minutes=30)

# API URLs
BASE_URL = "https://api.meridianenergy.co.nz"
LOGIN_URL = f"{BASE_URL}/oauth/token"
ACCOUNT_URL = f"{BASE_URL}/api/accounts"
PRICES_URL = f"{BASE_URL}/api/prices"
SOLAR_URL = f"{BASE_URL}/api/solar/generation"
HISTORY_URL = f"{BASE_URL}/api/solar/history"

# Add these constants
TOKEN_EXPIRY_BUFFER = 300  # 5 minutes buffer before token expiry
AUTH_FAILED_CODES = (401, 403)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Meridian Solar from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = MeridianSolarDataUpdateCoordinator(
        hass,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

class MeridianSolarDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Meridian Solar data."""

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        password: str,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.username = username
        self.password = password
        self._access_token = None
        self._account_id = None
        self._session = aiohttp.ClientSession()
        self._token_expires_at: datetime | None = None
        self._retry_count = 0
        self.MAX_RETRIES = 3

    async def _get_access_token(self) -> str:
        """Get access token from Meridian API."""
        try:
            async with async_timeout.timeout(30):
                auth_data = {
                    "grant_type": "password",
                    "username": self.username,
                    "password": self.password,
                    "client_id": "MeridianWebsite",
                }
                
                async with self._session.post(LOGIN_URL, data=auth_data) as response:
                    if response.status != 200:
                        raise UpdateFailed(f"Authentication failed: {response.status}")
                    data = await response.json()
                    
                    # Store token expiry time
                    expires_in = data.get("expires_in", 3600)
                    self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                    
                    return data["access_token"]
        except Exception as err:
            raise UpdateFailed(f"Error getting access token: {err}")

    async def _get_account_id(self) -> str:
        """Get the account ID."""
        if not self._access_token:
            self._access_token = await self._get_access_token()

        headers = {"Authorization": f"Bearer {self._access_token}"}
        
        try:
            async with async_timeout.timeout(30):
                async with self._session.get(ACCOUNT_URL, headers=headers) as response:
                    if response.status != 200:
                        raise UpdateFailed(f"Failed to get account ID: {response.status}")
                    data = await response.json()
                    return data[0]["id"]  # Assuming first account is the relevant one
        except Exception as err:
            raise UpdateFailed(f"Error getting account ID: {err}")

    async def _handle_api_call(self, url: str, headers: dict) -> dict[str, Any]:
        """Handle API calls with token refresh and retry logic."""
        try:
            # Check if token needs refresh
            if (self._token_expires_at and 
                datetime.now() + timedelta(seconds=TOKEN_EXPIRY_BUFFER) >= self._token_expires_at):
                self._access_token = await self._get_access_token()
                headers["Authorization"] = f"Bearer {self._access_token}"

            async with self._session.get(url, headers=headers) as response:
                if response.status in AUTH_FAILED_CODES and self._retry_count < self.MAX_RETRIES:
                    self._retry_count += 1
                    self._access_token = await self._get_access_token()
                    headers["Authorization"] = f"Bearer {self._access_token}"
                    return await self._handle_api_call(url, headers)
                
                if response.status != 200:
                    raise UpdateFailed(f"API call failed: {response.status}")
                
                self._retry_count = 0
                return await response.json()
                
        except Exception as err:
            raise UpdateFailed(f"API call failed: {err}")

    async def _async_update_data(self):
        """Fetch data from Meridian Solar API."""
        try:
            if not self._access_token:
                self._access_token = await self._get_access_token()
            
            if not self._account_id:
                self._account_id = await self._get_account_id()

            headers = {"Authorization": f"Bearer {self._access_token}"}
            
            async with async_timeout.timeout(30):
                # Get current and next rates
                prices_url = f"{PRICES_URL}/{self._account_id}"
                prices_data = await self._handle_api_call(prices_url, headers)
                
                # Get solar generation
                solar_url = f"{SOLAR_URL}/{self._account_id}"
                solar_data = await self._handle_api_call(solar_url, headers)

                # Process the data
                current_rate = prices_data.get("currentRate", 0.0)
                next_rate = prices_data.get("nextRate", 0.0)
                solar_generation = solar_data.get("currentGeneration", 0.0)

                return {
                    "current_rate": current_rate,
                    "next_rate": next_rate,
                    "solar_generation": solar_generation,
                }

        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    async def async_stop(self):
        """Close the session."""
        if self._session:
            await self._session.close()

    async def get_historical_data(self, days: int = 7) -> dict:
        """Get historical solar generation data."""
        if not self._access_token:
            self._access_token = await self._get_access_token()
        
        headers = {"Authorization": f"Bearer {self._access_token}"}
        params = {"days": days}
        
        url = f"{HISTORY_URL}/{self._account_id}"
        return await self._handle_api_call(url, headers, params=params) 