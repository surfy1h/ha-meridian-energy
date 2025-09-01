"""Diagnostics support for Meridian Solar."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Get diagnostics data from coordinator
    diagnostics = await coordinator.get_diagnostics_data()
    
    # Add config entry info (sanitized)
    diagnostics["config_entry"] = {
        "title": entry.title,
        "version": entry.version,
        "domain": entry.domain,
        "options": dict(entry.options),
        "state": entry.state.name,
        "disabled_by": entry.disabled_by,
        "unique_id": entry.unique_id,
    }
    
    # Add current data (if available)
    if coordinator.data:
        diagnostics["current_data"] = dict(coordinator.data)
    
    return diagnostics
