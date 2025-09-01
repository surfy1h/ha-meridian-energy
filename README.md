# Meridian Solar - Home Assistant Integration

A Home Assistant custom component for integrating with Meridian Energy's solar plan in New Zealand. This integration extracts real-time electricity rates and solar generation data from your Meridian Energy customer portal.

## ⚠️ Important Notice

This integration uses **web scraping** to extract data from the Meridian Energy customer portal since no public API is available. The integration:
- Logs into your customer portal using your credentials
- Extracts solar generation and usage data from the dashboard
- Updates Home Assistant sensors with this information

## Features

- **Current & Next Electricity Rates**: Monitor current electricity pricing
- **Solar Generation**: Track your solar panel generation
- **Secure Authentication**: Uses the same login as the customer portal
- **Configurable Updates**: Customizable polling intervals (default: 30 minutes)
- **Automatic Session Management**: Handles login sessions and re-authentication

## Prerequisites

- Active Meridian Energy account with online access
- Solar plan with Meridian Energy
- Access to the customer portal at `https://secure.meridianenergy.co.nz`

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/yourusername/ha-meridian-solar`
6. Select "Integration" as the category
7. Click "Add"
8. Search for "Meridian Solar" and install

### Manual Installation

1. Download the `custom_components/meridian_solar` folder
2. Copy it to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## Testing Your Credentials

**Before installing the integration**, test your credentials using the included test program:

```bash
cd test
python3 test_meridian_api.py your_username your_password
```

This will verify:
- ✅ Your credentials work with the portal
- ✅ The login process functions correctly
- ✅ Data can be extracted from your account
- ✅ Solar information is accessible

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Meridian Solar"
4. Enter your Meridian Energy credentials:
   - **Username**: Your Meridian Energy portal username (usually email)
   - **Password**: Your Meridian Energy portal password

## Sensors

The integration creates the following sensors:

| Sensor | Description | Unit | Data Source |
|--------|-------------|------|-------------|
| `sensor.meridian_solar_current_rate` | Current electricity rate | $/kWh | Portal dashboard |
| `sensor.meridian_solar_next_rate` | Next electricity rate | $/kWh | Portal dashboard |
| `sensor.meridian_solar_generation` | Current solar generation | kWh | Latest 30-min reading from CSV |
| `sensor.meridian_solar_daily_consumption` | Daily power consumption | kWh | Sum of today's consumption from CSV |
| `sensor.meridian_solar_daily_feed_in` | Daily solar feed-in | kWh | Sum of today's solar export from CSV |

## Configuration Options

After setup, you can configure:

- **Scan Interval**: How often to poll for updates (1-180 minutes, default: 30)
- **History Days**: Days of historical data to fetch (1-30 days, default: 7)

## How It Works

1. **Authentication**: Logs into the Meridian Energy customer portal
2. **Data Extraction**: Scrapes the dashboard for solar and usage information
3. **Pattern Matching**: Uses regex patterns to find relevant data
4. **Session Management**: Maintains login sessions and handles re-authentication
5. **Error Handling**: Gracefully handles portal changes and connection issues

## Troubleshooting

### Authentication Issues
- Verify your Meridian Energy portal credentials are correct
- Ensure you can log into `https://secure.meridianenergy.co.nz/login` manually
- Check that your account is not locked or suspended
- Run the test program to verify connectivity

### No Data Found
- Check the Home Assistant logs for error messages
- Verify your account has solar generation data in the portal
- The portal structure may have changed - check for updates
- Run the test program to see what data is available

### Connection Issues
- Verify your internet connection
- Check if the Meridian Energy portal is accessible
- Firewall or network restrictions may block access
- Try increasing the scan interval to reduce load

### Data Extraction Issues
- The portal HTML structure may have changed
- Check logs for regex pattern matching failures
- Solar data might be on a different page than expected
- Consider reporting issues for pattern updates

## Development and Testing

### Test Program

Use the included test program to debug issues:

```bash
cd test
./run_test.sh your_username your_password
```

Or create a `config.json` file:
```json
{
  "username": "your_username",
  "password": "your_password"
}
```

Then run: `python3 test_meridian_api.py`

### Debugging

Enable debug logging in Home Assistant:

```yaml
logger:
  default: info
  logs:
    custom_components.meridian_solar: debug
```

## Limitations

- **Web Scraping Dependency**: Relies on the current portal structure
- **No Historical Data**: Historical data extraction not yet implemented
- **Rate Limiting**: Respects reasonable polling intervals to avoid overloading the portal
- **Portal Changes**: May break if Meridian Energy updates their portal significantly

## Support

For issues and feature requests, please use the [GitHub Issues](https://github.com/yourusername/ha-meridian-solar/issues) page.

When reporting issues, please include:
- Home Assistant logs with debug enabled
- Output from the test program
- Your account type (solar plan details)

## Disclaimer

This integration is not officially affiliated with Meridian Energy. It uses web scraping techniques to extract data from the customer portal. Use at your own risk and ensure compliance with Meridian Energy's terms of service.

The integration is designed to be respectful of the portal resources and uses reasonable polling intervals.

## License

This project is licensed under the MIT License - see the LICENSE file for details.