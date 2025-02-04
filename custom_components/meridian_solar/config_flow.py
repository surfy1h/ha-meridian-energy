"""Config flow for Meridian Solar integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import callback

from .const import DOMAIN
from .coordinator import MeridianSolarDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Meridian Solar."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Create temporary coordinator to test credentials
                coordinator = MeridianSolarDataUpdateCoordinator(
                    self.hass,
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
                
                # Test authentication
                await coordinator.async_get_access_token()
                
                # Test account access
                await coordinator.async_get_account_id()
                
                await coordinator.async_stop()
                
                # If we get here, authentication was successful
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )
                
            except Exception as err:
                _LOGGER.error("Failed to authenticate: %s", err)
                errors["base"] = "auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "scan_interval",
                        default=self.config_entry.options.get("scan_interval", 30),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=180)),
                    vol.Optional(
                        "history_days",
                        default=self.config_entry.options.get("history_days", 7),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
                }
            ),
        ) 