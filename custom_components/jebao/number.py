"""Number platform for Jebao."""
from __future__ import annotations

import logging

from jebao import JebaoError

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
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
    """Set up Jebao number entities from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    device = data["device"]
    device_id = data["device_id"]
    model = data["model"]
    host = data["host"]

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

    # Create number entities
    async_add_entities(
        [
            JebaoFeedDurationNumber(coordinator, device_id, model, host, device),
        ]
    )


class JebaoFeedDurationNumber(JebaoEntity, NumberEntity):
    """Number entity for feed duration."""

    _attr_translation_key = "feed_duration"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 1
    _attr_native_max_value = 10
    _attr_native_step = 1

    def __init__(
        self,
        coordinator: JebaoDataUpdateCoordinator,
        device_id: str,
        model: str,
        host: str,
        device,
    ) -> None:
        """Initialize number entity."""
        super().__init__(coordinator, device_id, model, host)
        self._device = device
        self._attr_unique_id = f"{device_id}_feed_duration"
        self._attr_name = "Feed duration"
        self._attr_icon = "mdi:timer"
        self._value = 1  # Default value

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        try:
            minutes = int(value)
            await self._device.set_feed_duration(minutes)
            self._value = minutes
            self.async_write_ha_state()
            _LOGGER.info("Feed duration set to %d minutes", minutes)

        except JebaoError as err:
            _LOGGER.error("Failed to set feed duration: %s", err)
