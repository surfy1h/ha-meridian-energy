#!/usr/bin/env python3
"""
Test the Home Assistant integration exactly as it would run in HA
This simulates the real coordinator and sensors
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
import sys
import os

# Add the integration path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'custom_components', 'meridian_solar'))

# Set up logging like Home Assistant
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s (%(name)s) [%(filename)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Import the actual integration components
try:
    from __init__ import MeridianSolarDataUpdateCoordinator
    from sensor import (
        MeridianSolarRateSensor,
        MeridianSolarGenerationSensor, 
        MeridianSolarDailyConsumptionSensor,
        MeridianSolarDailyFeedInSensor,
        MeridianSolarAverageDailyUseSensor
    )
    print("✅ Successfully imported integration components")
except ImportError as e:
    print(f"❌ Failed to import integration: {e}")
    sys.exit(1)

class MockHass:
    """Mock Home Assistant object"""
    def __init__(self):
        self.data = {}

class MockConfigEntry:
    """Mock config entry"""
    def __init__(self, username, password):
        self.data = {
            "username": username,
            "password": password
        }
        self.options = {"scan_interval": 30}
        self.entry_id = "test_entry"

async def test_coordinator_and_sensors():
    """Test the coordinator and all sensors"""
    print("\n🚀 Testing Meridian Solar Home Assistant Integration")
    print("=" * 70)
    
    # Load config
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ Please create config.json with your real credentials first")
        return
    
    # Create mock HA objects
    hass = MockHass()
    entry = MockConfigEntry(config["username"], config["password"])
    
    # Create coordinator (like HA does)
    print("\n📡 Creating Data Coordinator...")
    coordinator = MeridianSolarDataUpdateCoordinator(
        hass,
        username=entry.data["username"],
        password=entry.data["password"],
        update_interval=timedelta(minutes=30)
    )
    
    # Test initial data fetch
    print("\n📥 Testing Initial Data Fetch...")
    try:
        await coordinator.async_config_entry_first_refresh()
        print("✅ Initial refresh successful!")
        
        if coordinator.data:
            print("📊 Retrieved data:")
            for key, value in coordinator.data.items():
                print(f"   {key}: {value}")
        else:
            print("⚠️ No data retrieved")
            
    except Exception as e:
        print(f"❌ Initial refresh failed: {e}")
        return
    
    # Create all sensors (like HA does)
    print("\n🔧 Creating Sensors...")
    sensors = [
        MeridianSolarRateSensor(coordinator, "current"),
        MeridianSolarRateSensor(coordinator, "next"), 
        MeridianSolarGenerationSensor(coordinator),
        MeridianSolarDailyConsumptionSensor(coordinator),
        MeridianSolarDailyFeedInSensor(coordinator),
        MeridianSolarAverageDailyUseSensor(coordinator),
    ]
    
    print(f"✅ Created {len(sensors)} sensors")
    
    # Test each sensor
    print("\n📊 Testing Sensor Values...")
    for sensor in sensors:
        try:
            name = sensor.name
            value = sensor.native_value
            unit = getattr(sensor, '_attr_native_unit_of_measurement', 'N/A')
            device_class = getattr(sensor, '_attr_device_class', 'N/A')
            state_class = getattr(sensor, '_attr_state_class', 'N/A')
            
            print(f"   🔹 {name}")
            print(f"      Value: {value} {unit}")
            print(f"      Device Class: {device_class}")
            print(f"      State Class: {state_class}")
            print()
            
        except Exception as e:
            print(f"   ❌ Error with sensor {sensor.name}: {e}")
    
    # Test data update cycle
    print("\n🔄 Testing Data Update Cycle...")
    try:
        await coordinator._async_update_data()
        print("✅ Data update successful!")
        
        # Show updated sensor values
        print("\n📊 Updated Sensor Values:")
        for sensor in sensors:
            value = sensor.native_value
            unit = getattr(sensor, '_attr_native_unit_of_measurement', '')
            print(f"   🔸 {sensor.name}: {value} {unit}")
            
    except Exception as e:
        print(f"❌ Data update failed: {e}")
    
    # Test diagnostics
    print("\n🔍 Testing Diagnostics...")
    try:
        diagnostics = await coordinator.get_diagnostics_data()
        print("✅ Diagnostics available:")
        for key, value in diagnostics.items():
            if isinstance(value, dict):
                print(f"   {key}: {len(value)} items")
            else:
                print(f"   {key}: {value}")
    except Exception as e:
        print(f"❌ Diagnostics failed: {e}")
    
    # Clean up
    print("\n🧹 Cleaning up...")
    await coordinator.async_stop()
    print("✅ Test completed!")

if __name__ == "__main__":
    asyncio.run(test_coordinator_and_sensors())
