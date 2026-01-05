"""Fan platform for Jebao pumps."""
from __future__ import annotations

import logging
from typing import Any

from jebao import JebaoError

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import CONF_DEVICE_ID, CONF_MODEL, DOMAIN
from .coordinator import JebaoDataUpdateCoordinator
from .entity import JebaoEntity

_LOGGER = logging.getLogger(__name__)

# MDP-20000 speed range is 30-100
SPEED_RANGE = (30, 100)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jebao fan from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    device = data["device"]
    device_id = data["device_id"]
    model = data["model"]
    host = data["host"]

    # Create coordinator
    scan_interval = entry.options.get("scan_interval")
    if scan_interval:
        coordinator = JebaoDataUpdateCoordinator(hass, device, scan_interval)
    else:
        coordinator = JebaoDataUpdateCoordinator(hass, device)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Create fan entity
    async_add_entities([JebaoPumpFan(coordinator, device_id, model, host, device)])


class JebaoPumpFan(JebaoEntity, FanEntity):
    """Jebao pump as a fan entity."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    )
    _attr_translation_key = "pump"

    def __init__(
        self,
        coordinator: JebaoDataUpdateCoordinator,
        device_id: str,
        model: str,
        host: str,
        device,
    ) -> None:
        """Initialize fan."""
        super().__init__(coordinator, device_id, model, host)
        self._device = device
        self._attr_unique_id = f"{device_id}_fan"
        self._attr_name = "Pump"

    @property
    def is_on(self) -> bool:
        """Return true if the entity is on."""
        return self.coordinator.data.get("is_on", False)

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        speed = self.coordinator.data.get("speed")
        if speed is None:
            return None

        # Convert device speed (30-100) to percentage (0-100)
        return ranged_value_to_percentage(SPEED_RANGE, speed)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        from jebao import DeviceState

        state = self.coordinator.data.get("state")
        attrs = {
            "device_state": state.name if state else "unknown",
            "raw_speed": self.coordinator.data.get("speed"),
        }

        # Add feed mode indicator
        if self.coordinator.data.get("is_feed_mode"):
            attrs["feed_mode"] = True

        return attrs

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the pump."""
        try:
            await self._device.turn_on()

            if percentage is not None:
                # Convert percentage (0-100) to device speed (30-100)
                speed = round(percentage_to_ranged_value(SPEED_RANGE, percentage))
                await self._device.set_speed(speed)

            await self.coordinator.async_request_refresh()

        except JebaoError as err:
            _LOGGER.error("Failed to turn on pump: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the pump."""
        try:
            await self._device.turn_off()
            await self.coordinator.async_request_refresh()

        except JebaoError as err:
            _LOGGER.error("Failed to turn off pump: %s", err)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the pump."""
        if percentage == 0:
            await self.async_turn_off()
            return

        try:
            # Convert percentage (0-100) to device speed (30-100)
            speed = round(percentage_to_ranged_value(SPEED_RANGE, percentage))
            await self._device.set_speed(speed)
            await self.coordinator.async_request_refresh()

        except JebaoError as err:
            _LOGGER.error("Failed to set pump speed: %s", err)
