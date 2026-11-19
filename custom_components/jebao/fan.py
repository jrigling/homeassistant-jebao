"""Fan platform for Jebao pumps."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DOMAIN, MAX_SPEED, MIN_SPEED
from .coordinator import JebaoDataUpdateCoordinator
from .entity import JebaoEntity

_LOGGER = logging.getLogger(__name__)

# The fan's 1-100% maps onto the pump's 30-100%; the Speed setting number uses the
# pump's own units
SPEED_RANGE = (MIN_SPEED, MAX_SPEED)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jebao fan from config entry."""
    coordinator: JebaoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([JebaoPumpFan(coordinator)])


class JebaoPumpFan(JebaoEntity, FanEntity):
    """Jebao pump as a fan entity."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    )
    _attr_translation_key = "pump"

    def __init__(self, coordinator: JebaoDataUpdateCoordinator) -> None:
        """Initialize fan."""
        super().__init__(coordinator, "fan")

    @property
    def is_on(self) -> bool:
        """On while the pump is switched on (running, feeding, or on its schedule)."""
        return self.coordinator.data.switch_on

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        speed = self.coordinator.data.motor_speed
        if not speed:
            return 0
        return ranged_value_to_percentage(SPEED_RANGE, max(speed, MIN_SPEED))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        state = self.coordinator.device.state
        status = self.coordinator.data
        return {
            "device_state": state.name if state else "unknown",
            "raw_speed": status.motor_speed,
            "feed_mode": status.feed_switch,
            "schedule": status.timer_on,
        }

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the pump."""

        async def command(device) -> None:
            await device.turn_on()
            if percentage:
                await device.set_speed(round(percentage_to_ranged_value(SPEED_RANGE, percentage)))

        await self.coordinator.async_command(command)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the pump."""
        await self.coordinator.async_command(lambda device: device.turn_off())

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the pump."""
        if percentage == 0:
            await self.async_turn_off()
            return
        speed = round(percentage_to_ranged_value(SPEED_RANGE, percentage))
        await self.coordinator.async_command(lambda device: device.set_speed(speed))
