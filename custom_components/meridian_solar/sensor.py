"""Support for Meridian Solar sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.device_registry import DeviceEntryType

from .const import DOMAIN, ATTR_CURRENT_RATE, ATTR_NEXT_RATE, ATTR_SOLAR_GENERATION, ATTR_DAILY_CONSUMPTION, ATTR_DAILY_FEED_IN, ATTR_AVERAGE_DAILY_USE

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Meridian Solar sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            MeridianSolarRateSensor(coordinator, "current"),
            MeridianSolarRateSensor(coordinator, "next"),
            MeridianSolarGenerationSensor(coordinator),
            MeridianSolarDailyConsumptionSensor(coordinator),
            MeridianSolarDailyFeedInSensor(coordinator),
            MeridianSolarAverageDailyUseSensor(coordinator),
        ]
    )

class MeridianSolarBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Meridian Solar sensors."""

    def __init__(self, coordinator, name, unique_id):
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_has_entity_name = True
        
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.username)},
            manufacturer="Meridian Energy",
            name="Meridian Solar",
            model="Solar Plan",
            configuration_url="https://secure.meridianenergy.co.nz/",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        return {
            "last_update": self.coordinator.last_update_success_time,
            "update_interval": self.coordinator.update_interval,
        }

class MeridianSolarRateSensor(MeridianSolarBaseSensor):
    """Representation of a Meridian Solar rate sensor."""

    def __init__(self, coordinator, rate_type):
        """Initialize the sensor."""
        super().__init__(coordinator, f"Meridian Solar {rate_type.title()} Rate", f"meridian_solar_{rate_type}_rate")
        self.rate_type = rate_type
        self._attr_native_unit_of_measurement = "$/kWh"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = None  # Monetary sensors should not use measurement state class

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        if self.rate_type == "current":
            return self.coordinator.data.get(ATTR_CURRENT_RATE)
        return self.coordinator.data.get(ATTR_NEXT_RATE)

class MeridianSolarGenerationSensor(MeridianSolarBaseSensor):
    """Representation of a Meridian Solar generation sensor."""

    def __init__(self, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator, "Meridian Solar Generation", "meridian_solar_generation")
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(ATTR_SOLAR_GENERATION)

class MeridianSolarDailyConsumptionSensor(MeridianSolarBaseSensor):
    """Representation of a Meridian Solar daily consumption sensor."""

    def __init__(self, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator, "Meridian Solar Daily Consumption", "meridian_solar_daily_consumption")
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(ATTR_DAILY_CONSUMPTION)

class MeridianSolarDailyFeedInSensor(MeridianSolarBaseSensor):
    """Representation of a Meridian Solar daily feed-in sensor."""

    def __init__(self, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator, "Meridian Solar Daily Feed In", "meridian_solar_daily_feed_in")
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(ATTR_DAILY_FEED_IN)

class MeridianSolarAverageDailyUseSensor(MeridianSolarBaseSensor):
    """Representation of a Meridian Solar average daily usage sensor."""

    def __init__(self, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator, "Meridian Solar Average Daily Use", "meridian_solar_average_daily_use")
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(ATTR_AVERAGE_DAILY_USE) 