# Troubleshooting Guide: "Unavailable" Sensors

## 🔍 Diagnosis Summary

The diagnostic script shows that **data extraction is working correctly**, which means the "Unavailable" sensors issue is likely related to Home Assistant configuration or coordinator state management.

## ✅ Step-by-Step Resolution

### **Step 1: Enable Enhanced Logging**

1. **Add logging configuration** to your `configuration.yaml`:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.meridian_solar: debug
       homeassistant.helpers.update_coordinator: debug
   ```

2. **Restart Home Assistant** completely (not just reload)

3. **Check logs** at Settings → System → Logs, filter for "meridian_solar"

### **Step 2: Update Integration to v2.2.4**

1. **Via HACS:**
   - Go to HACS → Integrations → Meridian Solar
   - Click "Update" if available

2. **Or manually:**
   - Copy updated files to `/config/custom_components/meridian_solar/`
   - Restart Home Assistant

### **Step 3: Force Sensor Update**

1. **Go to Developer Tools → Services**

2. **Run this service call:**
   ```yaml
   service: homeassistant.update_entity
   target:
     entity_id:
       - sensor.meridian_solar_current_rate
       - sensor.meridian_solar_next_rate  
       - sensor.meridian_solar_daily_consumption
       - sensor.meridian_solar_daily_feed_in
       - sensor.meridian_solar_generation
       - sensor.meridian_solar_average_daily_use
   ```

### **Step 4: Check Integration Configuration**

1. **Go to Settings → Integrations → Meridian Solar**
2. **Verify your credentials** are correct
3. **Try deleting and re-adding** the integration if needed

### **Step 5: Check Coordinator Status**

**Run this service call to check coordinator:**
```yaml
service: system_log.write
data:
  message: |
    Meridian Solar Sensors Status:
    - Current Rate: {{ states('sensor.meridian_solar_current_rate') }}
    - Next Rate: {{ states('sensor.meridian_solar_next_rate') }}  
    - Daily Consumption: {{ states('sensor.meridian_solar_daily_consumption') }}
    - Daily Feed In: {{ states('sensor.meridian_solar_daily_feed_in') }}
    - Solar Generation: {{ states('sensor.meridian_solar_generation') }}
    - Average Daily Use: {{ states('sensor.meridian_solar_average_daily_use') }}
  level: info
```

## 🔍 What to Look For in Logs

### **✅ Good Log Entries (Integration Working):**
- `🔄 Starting data update cycle...`
- `✅ Authentication successful`
- `✅ Valid CSV found at: https://secure.meridianenergy.co.nz/feed_in_report/download`
- `✅ Successfully extracted data from portal`
- `📊 Raw data: {'current_rate': 0.25, 'next_rate': 0.25, ...}`

### **❌ Problem Log Entries:**
- `❌ UpdateFailed exception: ...`
- `❌ Authentication error: ...`
- `❌ _extract_data_from_portal() returned None`
- `❌ Error updating data (attempt X/3): ...`

## 🎯 Expected Sensor Values

After fixes, sensors should show:
- **Current Rate**: `0.25 $/kWh` (default NZ rate)
- **Next Rate**: `0.25 $/kWh`
- **Daily Consumption**: `0.0 kWh` (no current day data available)
- **Daily Feed In**: `0.0 kWh` (no current solar export)
- **Solar Generation**: `0.0 kW` (normal at night/low generation)
- **Average Daily Use**: `0.0 kWh` (requires usage page data)

## 🚨 If Sensors Still Show "Unavailable"

### **Check These Common Issues:**

1. **Credentials Wrong in HA:**
   - Username/password incorrect in integration config
   - Account locked or requires verification

2. **Home Assistant Cache:**
   - Clear browser cache (Ctrl+Shift+R)
   - Restart HA completely

3. **Integration Not Loaded:**
   - Check HA logs for integration loading errors
   - Verify files are in correct location

4. **Coordinator Not Running:**
   - Integration may be disabled
   - Check for startup errors in logs

### **Last Resort - Clean Reinstall:**

1. **Remove integration** from Settings → Integrations
2. **Delete files**: `/config/custom_components/meridian_solar/`
3. **Restart HA**
4. **Reinstall** via HACS or manual copy
5. **Add integration** with fresh credentials

## 📞 Getting Help

If sensors still show "Unavailable" after these steps:

1. **Enable debug logging** (Step 1)
2. **Wait 30+ minutes** for coordinator to run
3. **Copy relevant log entries** that show errors
4. **Report issue** with logs at: https://github.com/surfy1h/ha-meridian-energy/issues

The diagnostic script confirms data extraction works, so the issue is likely in HA configuration or coordinator state management.
