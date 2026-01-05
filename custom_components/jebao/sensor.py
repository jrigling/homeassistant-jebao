"""Sensor platform for Jebao."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
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
    """Set up Jebao sensors from config entry."""
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
            coordinator = JebaoDataUpdateCoordinator(hass, device, entry, device_id, scan_interval)
        else:
            coordinator = JebaoDataUpdateCoordinator(hass, device, entry, device_id)
        await coordinator.async_config_entry_first_refresh()
        data["coordinator"] = coordinator
    else:
        coordinator = data["coordinator"]

    # Create sensors
    async_add_entities(
        [
            JebaoSpeedSensor(coordinator, device_id, model, host, mac_address, firmware_version),
            JebaoStateSensor(coordinator, device_id, model, host, mac_address, firmware_version),
        ]
    )


class JebaoSpeedSensor(JebaoEntity, SensorEntity):
    """Sensor for current pump speed."""

    _attr_translation_key = "speed"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

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
        self._attr_unique_id = f"{device_id}_speed"
        self._attr_name = "Speed"
        self._attr_icon = "mdi:speedometer"

    @property
    def native_value(self) -> int | None:
        """Return the current speed."""
        return self.coordinator.data.get("speed")


class JebaoStateSensor(JebaoEntity, SensorEntity):
    """Sensor for device state."""

    _attr_translation_key = "state"

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
        self._attr_unique_id = f"{device_id}_state"
        self._attr_name = "State"
        self._attr_icon = "mdi:information"

    @property
    def native_value(self) -> str | None:
        """Return the current state."""
        from jebao import DeviceState

        state = self.coordinator.data.get("state")
        if state is None:
            return None

        return state.name
