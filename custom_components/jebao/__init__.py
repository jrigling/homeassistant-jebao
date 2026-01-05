"""The Jebao integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from jebao import JebaoError, MDP20000Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo

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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Jebao from a config entry."""
    host = entry.data[CONF_HOST]
    device_id = entry.data.get("device_id")
    model = entry.data.get("model", "MDP-20000")

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
