# Jebao Aquarium Pumps for Home Assistant

Home Assistant custom integration for Jebao aquarium pumps with local network control.

## Features

- 🔍 **Automatic Discovery** - Scans all network interfaces for Jebao pumps
- 🌐 **Multi-Subnet Support** - Works with multiple VLANs and IoT networks
- 🔌 **Local Control** - Direct control without cloud dependency
- ⚡ **Real-Time Status** - Monitor pump state and speed
- 🐟 **Feed Mode** - Temporary pump pause with auto-resume
- 📅 **Pump Schedule** - Program and switch the pump's own 48-slot daily schedule, with its clock kept set
- 🚨 **Faults** - Overcurrent, running dry, stall and the pump's other fault bits
- 🏠 **Native HA Integration** - Configuration UI, device registry, etc.

## Supported Models

- **Jebao MDP-20000** - Variable-speed circulation pump
- **Jebao MDP-15000** - Variable-speed circulation pump (same protocol as the MDP-20000)
- **Jebao MDP-5000** - Variable-speed circulation pump (same datapoints as the MDP-15000)
- **Jebao MDP-3500** - Variable-speed circulation pump (same protocol; reported working in [#2](https://github.com/jrigling/homeassistant-jebao/issues/2))
- **Jebao MDP-2500** - Likely the same protocol ([#1](https://github.com/jrigling/homeassistant-jebao/issues/1), unconfirmed)
- **Jebao MD-4.4** - 4-channel dosing pump (planned)

These pumps all report the same product key and datapoints, so nothing on the network says which model a
pump is (the Jebao app doesn't know either). Discovery may label a pump MDP-20000: pick the right model
under **Configure** (Settings → Devices & services → Jebao). To tell several pumps apart, rename their
entries (the device takes the entry's name).

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

After adding a pump, you'll get these entities (IDs follow the device name):

### Fan (primary control)
- On/off and speed. The fan's 1-100% maps onto the pump's 30-100%.
- Attributes: device state (OFF/ON/FEED/PROGRAM), raw speed, feed mode, schedule

### Number
- **Speed setting** - Speed in the pump's own 30-100% units, as in the app. Like the app's slider,
  setting it while the schedule runs ends the schedule.
- **Feed duration** - How long feeding pauses the pump (1-60 minutes)

### Switch
- **Schedule** - Whether the pump follows its own daily schedule (the app's "Program"). The `slots`
  attribute holds the schedule.

### Buttons
- **Start feed** - Pause the pump for the feed duration. As in the app, this turns the schedule off.
- **Cancel feed** - End the pause early
- **Set pump clock** - Set the pump's clock to Home Assistant's time

### Binary sensors
- **Feed mode** - On while feeding
- **Problem** - On if the pump reports any fault (`faults` attribute lists them)
- Per-fault sensors (overcurrent, overvoltage, overtemperature, undervoltage, pump stalled, running dry,
  module communication) and **Wireless control** - diagnostic, disabled by default

### Sensors
- **Speed** - Current speed percentage
- **State** - OFF, ON, FEED or PROGRAM (on its schedule)
- **Schedule mode** - What the schedule is doing now: running, feeding or stopped (unknown while the
  schedule is off)
- **Schedule slots** - Number of slots in the schedule (diagnostic)
- **Pump clock last set** - What the pump's clock was last set to (diagnostic, disabled by default)

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
  value: 2  # 2 minutes (1-60)

# Start feed
service: button.press
target:
  entity_id: button.jebao_start_feed

# Cancel feed early
service: button.press
target:
  entity_id: button.jebao_cancel_feed
```

### Pump Schedule

The pump can run a daily schedule by itself, without Home Assistant: up to 48 time slots, each running
at a speed (30-100%), pausing for feeding, or stopped. Set it with the `jebao.set_schedule` service,
targeting the pump's **Schedule** switch:

```yaml
service: jebao.set_schedule
target:
  entity_id: switch.jebao_schedule
data:
  enable: true          # optional; leave out to keep the schedule on/off as it is
  slots:
    - start: "07:00"
      end: "21:00"
      speed: 80         # mode defaults to run
    - start: "21:00"
      end: "07:00"      # runs past midnight
      speed: 40
    - start: "12:00"    # slots must not overlap, so a feed pause splits a run slot
      end: "12:15"
      mode: feed
```

That example overlaps (12:00-12:15 is inside 07:00-21:00) and would be refused; split the day slot into
07:00-12:00 and 12:15-21:00 instead. An empty `slots` list clears the schedule.

The schedule runs on the pump's own clock, which nothing but the app's "Set Time" sets. With **Keep the
pump clock set** on (the default, under Configure), Home Assistant sets it at startup, every night at 03:17
(after any DST change), and before starting the schedule. **Set pump clock** does it on demand.

The integration leaves the pump in whatever mode it finds it; older versions took it out of its schedule
on every start.

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
4. Set the **Pump model** if discovery got it wrong
5. Adjust **scan_interval** (10-300 seconds, default: 30)
6. **Keep the pump clock set** (default on) - see [Pump Schedule](#pump-schedule)

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
1. Check pump is currently ON
2. Check the feed duration (1-60 minutes)
3. Check Home Assistant logs for error details

## Program Mode

Program mode is the pump's own schedule: see [Pump Schedule](#pump-schedule). The integration no longer
exits it on startup. Starting a feed or setting a manual speed ends it, as in the Jebao app; turn the
**Schedule** switch back on to resume.

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
