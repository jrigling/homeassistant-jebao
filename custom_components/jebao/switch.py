"""Switch platform for Jebao: the pump's own schedule."""
from __future__ import annotations

from typing import Any

from jebao import parse_slots
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.switch import SwitchEntity
from homeassistant.util import dt as dt_util

from .const import ATTR_ENABLE, ATTR_SLOTS, CONF_SYNC_CLOCK, DEFAULT_SYNC_CLOCK, DOMAIN, SERVICE_SET_SCHEDULE
from .coordinator import JebaoDataUpdateCoordinator
from .entity import JebaoEntity

SLOT_SCHEMA = vol.Schema(
    {
        vol.Required("start"): cv.string,
        vol.Required("end"): cv.string,
        vol.Optional("mode", default="run"): vol.In(["run", "feed", "off"]),
        vol.Optional("speed"): vol.All(vol.Coerce(int), vol.Range(min=30, max=100)),
    }
)
SET_SCHEDULE_SCHEMA = {
    vol.Required(ATTR_SLOTS): vol.All(cv.ensure_list, [SLOT_SCHEMA], vol.Length(max=48)),
    vol.Optional(ATTR_ENABLE): cv.boolean,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the schedule switch and the set_schedule service."""
    coordinator: JebaoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([JebaoScheduleSwitch(coordinator)])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_SCHEDULE, SET_SCHEDULE_SCHEMA, "async_set_schedule"
    )


class JebaoScheduleSwitch(JebaoEntity, SwitchEntity):
    """Whether the pump follows its own daily schedule (the app's "Program")."""

    _attr_translation_key = "schedule"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: JebaoDataUpdateCoordinator) -> None:
        """Initialize switch."""
        super().__init__(coordinator, "schedule")

    @property
    def is_on(self) -> bool:
        """Return true if the schedule is running."""
        return self.coordinator.data.timer_on

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The schedule itself, in the form set_schedule takes."""
        return {ATTR_SLOTS: [slot.as_dict() for slot in self.coordinator.data.schedule_slots]}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start the schedule."""
        await self._async_sync_clock_if_enabled()
        now = dt_util.now().replace(tzinfo=None)
        await self.coordinator.async_command(lambda device: device.set_schedule_enabled(True, now=now))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the schedule; the pump keeps its current speed."""
        await self.coordinator.async_command(lambda device: device.set_schedule_enabled(False))

    async def async_set_schedule(self, slots: list[dict], enable: bool | None = None) -> None:
        """Replace the pump's schedule (the set_schedule service)."""
        try:
            parsed = parse_slots(
                {**slot, "speed": slot.get("speed", 100)} if slot.get("mode", "run") == "run" else slot
                for slot in slots
            )
        except (KeyError, ValueError) as err:
            raise HomeAssistantError(f"Invalid schedule: {err}") from err
        if enable or (enable is None and self.coordinator.data.timer_on):
            await self._async_sync_clock_if_enabled()
        now = dt_util.now().replace(tzinfo=None)
        await self.coordinator.async_command(
            lambda device: device.set_schedule(parsed, enabled=enable, now=now)
        )

    async def _async_sync_clock_if_enabled(self) -> None:
        # The schedule runs on the pump's clock, so set it before relying on it
        if self.coordinator.entry.options.get(CONF_SYNC_CLOCK, DEFAULT_SYNC_CLOCK):
            await self.coordinator.async_sync_clock()
