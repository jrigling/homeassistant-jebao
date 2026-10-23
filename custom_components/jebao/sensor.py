"""Sensor platform for Jebao."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from jebao import AutoMode, PumpStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import JebaoDataUpdateCoordinator
from .entity import JebaoEntity

SCHEDULE_MODES = [mode.name.lower() for mode in AutoMode]


def _schedule_mode(status: PumpStatus) -> str | None:
    if not status.timer_on or status.auto_mode is None:
        return None
    return status.auto_mode.name.lower()


def _clock(status: PumpStatus) -> datetime | None:
    # The pump keeps its own time; this datapoint is what it was last set to
    if status.clock is None:
        return None
    return status.clock.replace(tzinfo=dt_util.get_default_time_zone())


@dataclass(frozen=True, kw_only=True)
class JebaoSensorDescription(SensorEntityDescription):
    """Describes a Jebao sensor."""

    value: Callable[[PumpStatus], Any]


DESCRIPTIONS: tuple[JebaoSensorDescription, ...] = (
    JebaoSensorDescription(
        key="speed",
        translation_key="speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:speedometer",
        value=lambda status: status.motor_speed,
    ),
    JebaoSensorDescription(
        key="schedule_mode",
        translation_key="schedule_mode",
        device_class=SensorDeviceClass.ENUM,
        options=SCHEDULE_MODES,
        icon="mdi:calendar-clock",
        value=_schedule_mode,
    ),
    JebaoSensorDescription(
        key="schedule_slots",
        translation_key="schedule_slots",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:calendar-text",
        value=lambda status: len(status.schedule_slots),
    ),
    JebaoSensorDescription(
        key="clock",
        translation_key="clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=_clock,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jebao sensors from config entry."""
    coordinator: JebaoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        [
            *(JebaoSensor(coordinator, description) for description in DESCRIPTIONS),
            JebaoStateSensor(coordinator),
        ]
    )


class JebaoSensor(JebaoEntity, SensorEntity):
    """A datapoint of the pump."""

    entity_description: JebaoSensorDescription

    def __init__(
        self,
        coordinator: JebaoDataUpdateCoordinator,
        description: JebaoSensorDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the datapoint."""
        return self.entity_description.value(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """The schedule's slots, on the slot count sensor."""
        if self.entity_description.key == "schedule_slots":
            return {"slots": [slot.as_dict() for slot in self.coordinator.data.schedule_slots]}
        return None


class JebaoStateSensor(JebaoEntity, SensorEntity):
    """Sensor for device state (OFF, ON, FEED or PROGRAM, i.e. on its schedule)."""

    _attr_translation_key = "state"
    _attr_icon = "mdi:information"

    def __init__(self, coordinator: JebaoDataUpdateCoordinator) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, "state")

    @property
    def native_value(self) -> str | None:
        """Return the current state."""
        state = self.coordinator.device.state
        return state.name if state is not None else None
