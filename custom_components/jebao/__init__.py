"""The Jebao integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from jebao import JebaoError, MDP20000Device, discover_devices

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.FAN,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
]

# Periodic background discovery interval (UDP broadcast scan)
DISCOVERY_INTERVAL = timedelta(minutes=5)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up periodic background discovery for Jebao pumps."""

    async def _periodic_discovery(_now=None) -> None:
        try:
            devices = await discover_devices(timeout=5.0)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.debug("Periodic discovery failed: %s", err)
            return

        entries = hass.config_entries.async_entries(DOMAIN)
        entries_by_id = {entry.unique_id: entry for entry in entries}

        for device in devices:
            if not device.is_mdp20000:
                continue

            existing = entries_by_id.get(device.device_id)
            if existing is not None:
                # Backfill missing MAC / update IP if it drifted (DHCP discovery is the
                # preferred IP-recovery path, but periodic scan is a belt-and-suspenders).
                updates: dict[str, Any] = {}
                if not existing.data.get("mac_address") and device.mac_address:
                    updates["mac_address"] = device.mac_address
                if existing.data.get(CONF_HOST) != device.ip_address:
                    updates[CONF_HOST] = device.ip_address
                if updates:
                    _LOGGER.info(
                        "Updating Jebao entry %s from periodic discovery: %s",
                        existing.title,
                        updates,
                    )
                    hass.config_entries.async_update_entry(
                        existing, data={**existing.data, **updates}
                    )
                continue

            # New, unconfigured pump - kick off a discovery flow so it appears
            # in Settings -> Devices & Services as "Discovered".
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_INTEGRATION_DISCOVERY},
                    data={
                        "device_id": device.device_id,
                        "ip": device.ip_address,
                        "model": device.model,
                        "mac_address": device.mac_address,
                        "firmware_version": device.firmware_version,
                    },
                )
            )

    # Fire once shortly after startup, then on the regular interval.
    hass.async_create_background_task(
        _periodic_discovery(), "jebao_initial_discovery"
    )
    async_track_time_interval(hass, _periodic_discovery, DISCOVERY_INTERVAL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Jebao from a config entry."""
    host = entry.data[CONF_HOST]
    device_id = entry.data.get("device_id")
    model = entry.data.get("model", "MDP-20000")
    mac_address = entry.data.get("mac_address")
    firmware_version = entry.data.get("firmware_version")

    _LOGGER.info("Setting up Jebao device at %s", host)

    # Create device instance
    device = MDP20000Device(host=host, device_id=device_id)

    try:
        # Connect to device
        await device.connect()

        # Ensure manual mode (exit Program mode if active)
        await device.ensure_manual_mode()

        _LOGGER.info("Successfully connected to Jebao device at %s", host)

    except JebaoError as err:
        _LOGGER.error("Failed to connect to Jebao device at %s: %s", host, err)
        await device.disconnect()
        raise ConfigEntryNotReady(f"Failed to connect: {err}") from err

    # Store device instance
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "device": device,
        "host": host,
        "device_id": device_id,
        "model": model,
        "mac_address": mac_address,
        "firmware_version": firmware_version,
    }

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Disconnect device
        data = hass.data[DOMAIN].pop(entry.entry_id)
        device: MDP20000Device = data["device"]
        await device.disconnect()
        _LOGGER.info("Disconnected from Jebao device at %s", data["host"])

    return unload_ok


def get_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Get device info for device registry."""
    device_id = entry.data.get("device_id", "unknown")
    model = entry.data.get("model", "MDP-20000")
    host = entry.data[CONF_HOST]

    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=entry.title,
        manufacturer="Jebao",
        model=model,
        configuration_url=f"http://{host}:12416",
    )
