# Credits and Acknowledgments

## Original Work

This Home Assistant integration builds upon the protocol foundation from:

### jebao-dosing-pump-md-4.4
- **Repository:** https://github.com/tancou/jebao-dosing-pump-md-4.4
- **Author:** [@tancou](https://github.com/tancou)
- **Language:** Node.js
- **License:** ISC

**What we learned:**
- GizWits IoT platform protocol basics
- Jebao pump communication patterns
- Authentication and connection management

### python-jebao
- **Repository:** https://github.com/jrigling/python-jebao
- **Author:** Justin Rigling
- **License:** MIT

This integration uses the python-jebao library, which provides:
- Multi-subnet device discovery
- Protocol implementation for MDP-20000
- All device control functionality

## Home Assistant Architecture

### Integration Pattern
Modern Home Assistant integration using:
- **Config Flow** - UI-based setup with discovery
- **Data Update Coordinator** - Efficient polling and entity updates
- **Device Registry** - Proper device grouping
- **Multiple Platforms** - Fan, sensors, buttons, number inputs

### Multi-Subnet Discovery
Special consideration for isolated IoT networks:
- Interface selection UI
- Per-interface UDP broadcasting
- Parallel discovery on multiple subnets
- No internet dependency

This feature was specifically designed for users running Home Assistant
with multiple network interfaces (e.g., main network + isolated IoT VLAN).

## Community Contributions

Thanks to:
- **Home Assistant Core Team** - For excellent integration patterns and documentation
- **HACS Team** - For making custom integrations easy to distribute
- **HA Community** - For feedback on integration design

## Testing

Integration tested with:
- 3x Jebao MDP-20000 pumps
- Multi-subnet network configuration
- Home Assistant 2024.1+

## Technical Stack

**Python Libraries:**
- `python-jebao` - Device control
- `homeassistant` - Core HA functionality
- `netifaces` - Network interface enumeration

**Home Assistant Platforms:**
- Fan - Primary pump control
- Binary Sensor - Feed mode status
- Button - Feed control actions
- Number - Feed duration configuration
- Sensor - Speed and state monitoring

## Integration Features

### Implemented
- ✅ Multi-subnet UDP discovery
- ✅ Manual IP configuration fallback
- ✅ Fan entity with speed control (30-100%)
- ✅ Feed mode support
- ✅ Program mode auto-exit
- ✅ Status monitoring
- ✅ Device registry integration
- ✅ Options flow (scan interval)
- ✅ HACS compatibility

### Planned
- ⏳ MD 4.4 dosing pump support
- ⏳ Device triggers (feed started/ended)
- ⏳ Diagnostics integration
- ⏳ Service for advanced control

## Design Decisions

**Fan Platform Choice:**
Pump represented as Fan entity rather than Switch + Number because:
- Native speed slider in UI
- Percentage conversion handled by HA core
- Consistent with other variable-speed devices
- Better UX

**Coordinator Pattern:**
Single coordinator for multiple entities:
- One status request per update interval
- All entities update together
- Reduced network traffic
- Follows HA best practices

**Multi-Subnet UI:**
Interface selection during setup:
- Users control which networks to scan
- Critical for isolated IoT VLANs
- Better than auto-discover-everything approach

## Legal

This is an unofficial integration, not affiliated with:
- Jebao / Jecod
- Home Assistant
- GizWits IoT platform
- The original jebao-dosing-pump-md-4.4 project

Integration created for interoperability and home automation purposes.

**Device warranty:** May be affected by third-party control software. Use at own risk.

---

**homeassistant-jebao** - Home Assistant integration for Jebao pumps
Copyright (c) 2026 Justin Rigling
MIT License
