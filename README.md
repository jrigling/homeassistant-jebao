# Jebao Aquarium Pumps for Home Assistant

Home Assistant custom integration for Jebao aquarium pumps with local network control.

## Features

- 🔍 **Automatic Discovery** - Scans all network interfaces for Jebao pumps
- 🌐 **Multi-Subnet Support** - Works with multiple VLANs and IoT networks
- 🔌 **Local Control** - Direct control without cloud dependency
- ⚡ **Real-Time Status** - Monitor pump state and speed
- 🐟 **Feed Mode** - Temporary pump pause with auto-resume
- 🏠 **Native HA Integration** - Configuration UI, device registry, etc.

## Supported Models

- **Jebao MDP-20000** - Variable-speed circulation pump
- **Jebao MD-4.4** - 4-channel dosing pump (planned)

## Installation

### HACS (Recommended)

1. Open HACS
2. Go to "Integrations"
3. Click the three dots in the top right
4. Select "Custom repositories"
5. Add repository URL: `https://github.com/jrigling/homeassistant-jebao`
6. Category: Integration
7. Click "Add"
8. Search for "Jebao" and install

### Manual Installation

1. Copy the `custom_components/jebao` directory to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

### Automatic Discovery (Recommended)

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **Jebao**
4. Select **Automatic discovery**
5. Choose which network interfaces to scan (or select all)
6. Select your pump from the discovered devices
7. Click **Submit**

### Manual Configuration

If discovery doesn't work or you prefer manual setup:

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **Jebao**
4. Select **Manual configuration**
5. Enter the IP address of your pump
6. Click **Submit**

## Multi-Subnet Setup

If your Home Assistant server has multiple network interfaces (e.g., main network + IoT VLAN):

**Example:**
- Main network: `192.168.1.0/24` on `eth0`
- IoT network: `10.20.20.0/24` on `eth1` (pumps here)

During discovery:
1. You'll see both interfaces listed with their IP addresses
2. Select **both** `eth0` and `eth1` (or just `eth1` if pumps are only on IoT network)
3. Discovery will broadcast on all selected interfaces
4. Pumps respond within 2 seconds

**Why this matters:**
- Standard discovery only broadcasts on the default interface
- With multiple interfaces, you control which networks to scan
- Perfect for isolated IoT networks that block internet access

## Entities

After adding a pump, you'll get these entities:

### Fan Entity (Primary Control)
- **Entity ID:** `fan.jebao_pump`
- **Controls:**
  - Turn on/off
  - Set speed (30-100%)
- **Attributes:**
  - Device state (OFF/ON/FEED/PROGRAM)
  - Raw speed value
  - Feed mode indicator

### Binary Sensor
- **Entity ID:** `binary_sensor.jebao_feed_mode`
- **State:** On when pump is in feed mode

### Buttons
- **Start Feed:** `button.jebao_start_feed` - Start feed mode
- **Cancel Feed:** `button.jebao_cancel_feed` - Cancel and resume

### Number
- **Feed Duration:** `number.jebao_feed_duration` - Set duration (1-10 minutes)

### Sensors
- **Speed:** `sensor.jebao_speed` - Current speed percentage
- **State:** `sensor.jebao_state` - Current device state

## Usage Examples

### Basic Control

```yaml
# Turn on pump at 75%
service: fan.turn_on
target:
  entity_id: fan.jebao_pump
data:
  percentage: 75

# Turn off pump
service: fan.turn_off
target:
  entity_id: fan.jebao_pump

# Set speed (while running)
service: fan.set_percentage
target:
  entity_id: fan.jebao_pump
data:
  percentage: 50
```

### Feed Mode

```yaml
# Configure feed duration
service: number.set_value
target:
  entity_id: number.jebao_feed_duration
data:
  value: 2  # 2 minutes

# Start feed
service: button.press
target:
  entity_id: button.jebao_start_feed

# Cancel feed early
service: button.press
target:
  entity_id: button.jebao_cancel_feed
```

### Automations

#### Automatic Feed Schedule

```yaml
automation:
  - alias: "Daily aquarium feeding"
    trigger:
      - platform: time
        at: "08:00:00"
      - platform: time
        at: "18:00:00"
    action:
      - service: button.press
        target:
          entity_id: button.jebao_start_feed
```

#### Night Mode (Reduce Flow)

```yaml
automation:
  - alias: "Aquarium night mode"
    trigger:
      - platform: time
        at: "22:00:00"
    condition:
      - condition: state
        entity_id: fan.jebao_pump
        state: "on"
    action:
      - service: fan.set_percentage
        target:
          entity_id: fan.jebao_pump
        data:
          percentage: 30  # Minimum speed

  - alias: "Aquarium day mode"
    trigger:
      - platform: time
        at: "08:00:00"
    action:
      - service: fan.turn_on
        target:
          entity_id: fan.jebao_pump
        data:
          percentage: 75  # Normal daytime speed
```

#### Feed Mode Notification

```yaml
automation:
  - alias: "Feed mode started"
    trigger:
      - platform: state
        entity_id: binary_sensor.jebao_feed_mode
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "Aquarium"
          message: "Feed mode started - pump paused"

  - alias: "Feed mode ended"
    trigger:
      - platform: state
        entity_id: binary_sensor.jebao_feed_mode
        to: "off"
    action:
      - service: notify.mobile_app
        data:
          title: "Aquarium"
          message: "Feed mode ended - pump resumed"
```

## Lovelace Cards

### Simple Control Card

```yaml
type: entities
title: Aquarium Pump
entities:
  - entity: fan.jebao_pump
  - entity: sensor.jebao_speed
  - entity: binary_sensor.jebao_feed_mode
  - entity: button.jebao_start_feed
```

### Advanced Control Card

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Pump Control
    entities:
      - entity: fan.jebao_pump
        name: Power
      - type: custom:slider-entity-row
        entity: fan.jebao_pump
        name: Speed
        icon: mdi:speedometer

  - type: entities
    title: Feed Mode
    entities:
      - entity: binary_sensor.jebao_feed_mode
        name: Active
      - entity: number.jebao_feed_duration
        name: Duration
      - entity: button.jebao_start_feed
        name: Start
      - entity: button.jebao_cancel_feed
        name: Cancel
```

## Configuration Options

After adding the integration, you can configure:

1. Go to **Settings** → **Devices & Services**
2. Find **Jebao** integration
3. Click **Configure**
4. Adjust **scan_interval** (10-300 seconds, default: 30)

Lower intervals = more responsive, but more network traffic.

## Troubleshooting

### Discovery Fails

**Problem:** No devices found during discovery

**Solutions:**
1. Ensure pump is powered on and connected to network
2. Check pump has IP address (may need DHCP reservation)
3. Try manual configuration with known IP address
4. Check firewall allows UDP port 12414 broadcast
5. Verify selected network interfaces are correct

### Cannot Connect

**Problem:** "Failed to connect" error

**Solutions:**
1. Verify IP address is correct
2. Ensure TCP port 12416 is accessible
3. Check pump is not in use by official app (close app)
4. Try power cycling the pump
5. Check Home Assistant can reach the subnet

### Multiple Interfaces Not Working

**Problem:** Discovery only finds devices on one network

**Solutions:**
1. During setup, explicitly select ALL interfaces
2. Check each interface has proper routing
3. Verify broadcasts are allowed on each interface
4. For VLANs, ensure broadcast domain is correct

### Pump Becomes Unavailable

**Problem:** Entities show "unavailable"

**Solutions:**
1. Check network connectivity
2. Verify pump hasn't changed IP (use DHCP reservation)
3. Check Home Assistant logs for errors
4. Restart integration from Devices & Services
5. Power cycle pump if unresponsive

### Feed Mode Doesn't Start

**Problem:** Feed button has no effect

**Solutions:**
1. Ensure pump is in manual mode (not Program mode)
2. Check pump is currently ON
3. Set feed duration first (1-10 minutes)
4. Check Home Assistant logs for error details

## Program Mode

If your pump is in **Program mode** (schedule-based operation):

- The integration will automatically exit Program mode on startup
- This ensures manual control via Home Assistant works
- Your pump's schedule is preserved but not active
- You can re-enable Program mode from official app if desired

**Best practice:** Use Home Assistant automations instead of pump's Program mode for better integration and flexibility.

## IoT Network Considerations

This integration is **perfect for isolated IoT networks**:

- ✅ No internet required - works entirely local
- ✅ Multi-VLAN support built-in
- ✅ No cloud dependencies
- ✅ Direct TCP/UDP control

**Example setup:**
```
Home Assistant: 192.168.1.50
  - eth0: 192.168.1.0/24 (main network, has internet)
  - eth1: 10.20.20.0/24 (IoT VLAN, blocked from internet)

Jebao Pumps: 10.20.20.12, 10.20.20.13, 10.20.20.17
  - On IoT VLAN
  - Cannot reach internet (firewall blocked)
  - Can communicate with HA on eth1
```

Discovery will work because:
- HA sends broadcasts on eth1 (IoT subnet)
- Pumps respond on same subnet
- No internet needed

## Dependencies

- `python-jebao` - The underlying Python library
- `netifaces` - For multi-interface network discovery

Both are installed automatically.

## Support

- **Issues:** [GitHub Issues](https://github.com/jrigling/homeassistant-jebao/issues)
- **Discussions:** [GitHub Discussions](https://github.com/jrigling/homeassistant-jebao/discussions)
- **Documentation:** [Protocol Docs](https://github.com/jrigling/python-jebao)

## Credits

This integration builds upon the excellent work from:
- [jebao-dosing-pump-md-4.4](https://github.com/tancou/jebao-dosing-pump-md-4.4) by [@tancou](https://github.com/tancou) - Original Node.js implementation for MD 4.4 pumps that provided the foundation for understanding the GizWits protocol

Protocol for MDP-20000 was reverse-engineered through packet capture analysis of the official Jebao mobile app. Thanks to the Home Assistant community for feedback and testing.

## License

MIT License

## Disclaimer

This is an unofficial integration not affiliated with Jebao. Use at your own risk. Device warranty may be affected by third-party control software.
