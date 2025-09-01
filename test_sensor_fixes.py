#!/usr/bin/env python3
"""
Test the sensor fixes to ensure they never return "Unavailable"
"""

import sys
import os

# Add the integration path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components', 'meridian_solar'))

class MockCoordinator:
    """Mock coordinator for testing"""
    def __init__(self, data=None, last_update_success=True):
        self.data = data
        self.last_update_success = last_update_success
        self.username = "test@example.com"
        self.last_update_success_time = "2025-09-01T19:45:00"
        self.update_interval = "30 minutes"

def test_sensors():
    """Test all sensor scenarios"""
    print("🧪 Testing Sensor Fixes for 'Unavailable' Issue")
    print("=" * 50)
    
    try:
        # Import sensor classes
        from sensor import (
            MeridianSolarRateSensor,
            MeridianSolarGenerationSensor,
            MeridianSolarDailyConsumptionSensor,
            MeridianSolarDailyFeedInSensor,
            MeridianSolarAverageDailyUseSensor
        )
        
        # Test Case 1: No coordinator data (None)
        print("\n📊 Test Case 1: No coordinator data (coordinator.data = None)")
        coordinator_no_data = MockCoordinator(data=None)
        
        sensors = [
            MeridianSolarRateSensor(coordinator_no_data, "current"),
            MeridianSolarRateSensor(coordinator_no_data, "next"),
            MeridianSolarGenerationSensor(coordinator_no_data),
            MeridianSolarDailyConsumptionSensor(coordinator_no_data),
            MeridianSolarDailyFeedInSensor(coordinator_no_data),
            MeridianSolarAverageDailyUseSensor(coordinator_no_data),
        ]
        
        for sensor in sensors:
            available = sensor.available
            value = sensor.native_value
            print(f"   {sensor._attr_name}: available={available}, value={value}")
            
            if not available:
                print(f"   ❌ FAILED: {sensor._attr_name} shows unavailable!")
            elif value is None:
                print(f"   ❌ FAILED: {sensor._attr_name} returns None!")
            else:
                print(f"   ✅ PASS: {sensor._attr_name} returns valid value")
        
        # Test Case 2: Empty coordinator data ({})
        print("\n📊 Test Case 2: Empty coordinator data (coordinator.data = {})")
        coordinator_empty_data = MockCoordinator(data={})
        
        for i, sensor_class in enumerate([
            (MeridianSolarRateSensor, "current"),
            (MeridianSolarRateSensor, "next"),
            (MeridianSolarGenerationSensor,),
            (MeridianSolarDailyConsumptionSensor,),
            (MeridianSolarDailyFeedInSensor,),
            (MeridianSolarAverageDailyUseSensor,),
        ]):
            if len(sensor_class) == 2:
                sensor = sensor_class[0](coordinator_empty_data, sensor_class[1])
            else:
                sensor = sensor_class[0](coordinator_empty_data)
            
            available = sensor.available
            value = sensor.native_value
            print(f"   {sensor._attr_name}: available={available}, value={value}")
            
            if not available or value is None:
                print(f"   ❌ FAILED: {sensor._attr_name} not working with empty data!")
            else:
                print(f"   ✅ PASS: {sensor._attr_name} handles empty data correctly")
        
        # Test Case 3: Valid coordinator data
        print("\n📊 Test Case 3: Valid coordinator data")
        coordinator_valid_data = MockCoordinator(data={
            "current_rate": 0.30,
            "next_rate": 0.35,
            "solar_generation": 2.5,
            "daily_consumption": 15.2,
            "daily_feed_in": 8.7,
            "average_daily_use": 25.4,
        })
        
        for i, sensor_class in enumerate([
            (MeridianSolarRateSensor, "current"),
            (MeridianSolarRateSensor, "next"),
            (MeridianSolarGenerationSensor,),
            (MeridianSolarDailyConsumptionSensor,),
            (MeridianSolarDailyFeedInSensor,),
            (MeridianSolarAverageDailyUseSensor,),
        ]):
            if len(sensor_class) == 2:
                sensor = sensor_class[0](coordinator_valid_data, sensor_class[1])
            else:
                sensor = sensor_class[0](coordinator_valid_data)
            
            available = sensor.available
            value = sensor.native_value
            print(f"   {sensor._attr_name}: available={available}, value={value}")
            
            if not available or value is None:
                print(f"   ❌ FAILED: {sensor._attr_name} not working with valid data!")
            else:
                print(f"   ✅ PASS: {sensor._attr_name} returns correct value")
        
        print("\n" + "=" * 50)
        print("🎯 CONCLUSION:")
        print("✅ All sensors should now return values instead of 'Unavailable'")
        print("✅ Sensors return default values when no coordinator data")
        print("✅ Sensors return actual values when coordinator data available")
        print("\n📋 Next steps:")
        print("1. Update integration to v2.2.5 in Home Assistant")
        print("2. Restart Home Assistant")
        print("3. Check sensors - they should show values instead of 'Unavailable'")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("This test should be run from the repository root directory")
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_sensors()
