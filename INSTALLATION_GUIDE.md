# Jebao Home Assistant Integration - Installation Guide

## Current Status: ✅ READY FOR TESTING

The integration is ready for testing with HACS. When installed via HACS, the Python library is automatically installed from GitHub.

## Prerequisites

- Home Assistant 2024.1.0 or later
- HACS installed
- Jebao MDP-20000 pump(s) on your network
- Network access to pump(s) on port 12416

## Installation Steps

### Option 1: HACS Custom Repository (Recommended for Testing)

1. **Add Custom Repository to HACS**
   - Open HACS in Home Assistant
   - Click the 3 dots menu (top right)
   - Select "Custom repositories"
   - Add repository URL: `https://github.com/jrigling/homeassistant-jebao`
   - Category: Integration
   - Click "Add"

2. **Install the Integration via HACS**
   - Go to HACS > Integrations
   - Search for "Jebao"
   - Click "Download"
   - Restart Home Assistant

   **Note:** The `python-jebao` library will be automatically installed from GitHub during this step.

3. **Add Integration**
   - Go to Settings > Devices & Services
   - Click "+ Add Integration"
   - Search for "Jebao"
   - Follow the setup flow

### Option 2: Manual Installation (For Development)

**Note:** Manual installation requires you to install the Python library separately.

1. **Install Python Library**

   **For Home Assistant OS/Supervised:**
   ```bash
   # SSH into Home Assistant, then:
   docker exec -it homeassistant bash
   pip install git+https://github.com/jrigling/python-jebao.git@main
   exit
   ```

   **For Home Assistant Core (venv):**
   ```bash
   source /path/to/homeassistant/venv/bin/activate
   pip install git+https://github.com/jrigling/python-jebao.git@main
   ```

   **For Home Assistant Container:**
   ```bash
   docker exec homeassistant pip install git+https://github.com/jrigling/python-jebao.git@main
   ```

2. **Copy Integration Files**
   ```bash
   # Clone the repository and copy to HA config directory
   git clone https://github.com/jrigling/homeassistant-jebao.git
   cp -r homeassistant-jebao/custom_components/jebao \
         /path/to/homeassistant/config/custom_components/
   ```

3. **Restart Home Assistant**

4. **Add Integration** (same as above)

## Configuration

### Discovery (Recommended)

The integration will automatically discover Jebao pumps on your network:

1. Click "+ Add Integration"
2. Search for "Jebao"
3. Select "Automatic Discovery"
4. Wait for pumps to be discovered (2-3 seconds)
5. Select pump(s) to add
6. Configure polling interval (default: 30 seconds)

### Manual Configuration

If discovery doesn't find your pump:

1. Click "+ Add Integration"
2. Search for "Jebao"
3. Select "Manual Configuration"
4. Enter:
   - **Host**: Pump IP address (e.g., 10.20.20.12)
   - **Model**: MDP-20000
5. Click "Submit"

## Entities Created

For each MDP-20000 pump, the integration creates:

### Fan Entity (Primary Control)
- **Entity ID**: `fan.jebao_pump`
- **Features**:
  - Turn ON/OFF
  - Set speed (0-100% in UI, maps to 30-100% on device)
- **Attributes**:
  - `device_state`: Current state (ON, OFF, FEED, PROGRAM)
  - `raw_speed`: Actual device speed (30-100)
  - `feed_mode`: Present if in feed mode

### Binary Sensors
- **Feed Mode Active**: Shows if pump is in feed mode
- **Manual Mode**: Shows if pump is in manual control mode

### Buttons
- **Feed Mode Start**: Start 1-minute feed mode
- **Feed Mode Cancel**: Cancel feed mode
- **Exit Program Mode**: Exit program mode to manual

### Numbers
- **Feed Duration**: Set feed mode duration (1-10 minutes)

### Sensors
- **State**: Current pump state (OFF, ON, FEED, PROGRAM)
- **Speed**: Current speed percentage

## Usage Examples

### Automations

**Turn on pump at sunrise:**
```yaml
automation:
  - alias: "Pool Pump On at Sunrise"
    trigger:
      - platform: sun
        event: sunrise
    action:
      - service: fan.turn_on
        target:
          entity_id: fan.jebao_pump
        data:
          percentage: 75
```

**Feed mode during feeding time:**
```yaml
automation:
  - alias: "Feed Mode During Fish Feeding"
    trigger:
      - platform: time
        at: "08:00:00"
    action:
      - service: button.press
        target:
          entity_id: button.jebao_pump_feed_mode_start
```

**Adjust speed based on time of day:**
```yaml
automation:
  - alias: "Daytime Full Speed"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: fan.set_percentage
        target:
          entity_id: fan.jebao_pump
        data:
          percentage: 100

  - alias: "Nighttime Low Speed"
    trigger:
      - platform: time
        at: "22:00:00"
    action:
      - service: fan.set_percentage
        target:
          entity_id: fan.jebao_pump
        data:
          percentage: 40  # Maps to 42% actual device speed
```

## Troubleshooting

### Integration Not Found
- Ensure HACS is installed and working
- Check that custom repository was added correctly
- Restart Home Assistant after installing via HACS

### "Module 'jebao' not found"
- The python-jebao library is not installed
- Follow step 2 in installation to install the library
- Restart Home Assistant after installing

### Pump Not Discovered
- Ensure pump is powered on and connected to network
- Check that Home Assistant can reach pump IP (ping test)
- Verify port 12416 is not blocked by firewall
- Try manual configuration with pump's IP address

### Connection Timeouts
- Check pump IP address is correct
- Ensure pump is not in use by another application
- Try power cycling the pump
- Check Home Assistant logs for detailed error messages

### Commands Fail with "Lost message synchronization"
- This is rare with automatic retry (3 attempts)
- If persistent, power cycle the pump
- Check for network issues between HA and pump
- Increase polling interval to reduce load

### State Not Updating
- Check polling interval in integration options
- Verify pump is responding (check logs)
- Try reloading the integration

## Advanced Configuration

### Adjust Polling Interval

1. Go to Settings > Devices & Services
2. Find Jebao integration
3. Click "Configure"
4. Adjust "Scan Interval" (default: 30 seconds)
5. Lower values = more responsive, but more network traffic

### Multiple Pumps

The integration supports multiple pumps simultaneously:

1. Add each pump as a separate integration instance
2. Each pump will have unique entity IDs
3. Pumps operate independently

### Debug Logging

To enable debug logging for troubleshooting:

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.jebao: debug
    jebao: debug
```

## Known Limitations

1. **Feed Mode**: May require 2-3 retry attempts due to garbage bytes (automatic)
2. **MDP-20000 Only**: MD-4.4 dosing pumps not yet supported
3. **Local Polling**: No push notifications from pump (polls every 30s by default)
4. **Speed Range**: Pump enforces 30-100% range (lower speeds map to 30%)

## Support

- **Issues**: https://github.com/jrigling/homeassistant-jebao/issues
- **Logs**: Enable debug logging (see above) and check Home Assistant logs

## Version History

### 0.1.0 (Initial Release)
- MDP-20000 support
- Fan entity for ON/OFF and speed control
- Feed mode buttons
- Auto-discovery via UDP broadcast
- Manual configuration option
- Automatic retry on transient failures
- Multi-pump support
