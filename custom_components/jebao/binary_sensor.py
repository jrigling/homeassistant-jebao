"""Binary sensor platform for Jebao."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICE_ID, CONF_MODEL, DOMAIN
from .coordinator import JebaoDataUpdateCoordinator
from .entity import JebaoEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jebao binary sensors from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    device = data["device"]
    device_id = data["device_id"]
    model = data["model"]
    host = data["host"]
    mac_address = data.get("mac_address")
    firmware_version = data.get("firmware_version")

    # Get or create coordinator
    if "coordinator" not in data:
        scan_interval = entry.options.get("scan_interval")
        if scan_interval:
            coordinator = JebaoDataUpdateCoordinator(hass, device, scan_interval)
        else:
            coordinator = JebaoDataUpdateCoordinator(hass, device)
        await coordinator.async_config_entry_first_refresh()
        data["coordinator"] = coordinator
    else:
        coordinator = data["coordinator"]

    # Create binary sensors
    async_add_entities(
        [
            JebaoFeedModeSensor(coordinator, device_id, model, host, mac_address, firmware_version),
        ]
    )


class JebaoFeedModeSensor(JebaoEntity, BinarySensorEntity):
    """Binary sensor for feed mode status."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "feed_mode"

    def __init__(
        self,
        coordinator: JebaoDataUpdateCoordinator,
        device_id: str,
        model: str,
        host: str,
        mac_address: str | None = None,
        firmware_version: str | None = None,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, device_id, model, host, mac_address, firmware_version)
        self._attr_unique_id = f"{device_id}_feed_mode"
        self._attr_name = "Feed mode"

    @property
    def is_on(self) -> bool:
        """Return true if in feed mode."""
        return self.coordinator.data.get("is_feed_mode", False)
