"""Number platform for Jebao."""
from __future__ import annotations

from jebao.datapoints import MAX_FEED_TIME, MIN_FEED_TIME

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_SPEED, MIN_SPEED
from .coordinator import JebaoDataUpdateCoordinator
from .entity import JebaoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jebao number entities from config entry."""
    coordinator: JebaoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([JebaoFeedDurationNumber(coordinator), JebaoSpeedNumber(coordinator)])


class JebaoFeedDurationNumber(JebaoEntity, NumberEntity):
    """How long feed mode pauses the pump (the pump's FeedTime)."""

    _attr_translation_key = "feed_duration"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = MIN_FEED_TIME
    _attr_native_max_value = MAX_FEED_TIME
    _attr_native_step = 1
    _attr_icon = "mdi:timer"

    def __init__(self, coordinator: JebaoDataUpdateCoordinator) -> None:
        """Initialize number entity."""
        super().__init__(coordinator, "feed_duration")

    @property
    def native_value(self) -> float | None:
        """Return the pump's feed duration."""
        return self.coordinator.data.feed_time

    async def async_set_native_value(self, value: float) -> None:
        """Set the feed duration (doesn't start feeding)."""
        await self.coordinator.async_command(lambda device: device.set_feed_time(int(value)))


class JebaoSpeedNumber(JebaoEntity, NumberEntity):
    """Number entity for the pump speed in the device's own 30-100% units.

    The fan entity rescales 30-100 onto 0-100 (speed 30 shows as 1%), which
    doesn't match the Jebao app; this sets the speed exactly as the app does.
    Like the app's slider, setting it while the schedule runs ends the schedule.
    """

    _attr_translation_key = "speed"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = MIN_SPEED
    _attr_native_max_value = MAX_SPEED
    _attr_native_step = 1
    _attr_icon = "mdi:speedometer"

    def __init__(self, coordinator: JebaoDataUpdateCoordinator) -> None:
        """Initialize number entity."""
        super().__init__(coordinator, "speed_setting")

    @property
    def native_value(self) -> float | None:
        """Return the current speed."""
        return self.coordinator.data.motor_speed

    async def async_set_native_value(self, value: float) -> None:
        """Set the pump speed."""
        await self.coordinator.async_command(lambda device: device.set_speed(int(value)))
