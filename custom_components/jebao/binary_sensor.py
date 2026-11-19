"""Binary sensor platform for Jebao."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from jebao import PumpStatus
from jebao.datapoints import FAULT_NAMES

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import JebaoDataUpdateCoordinator
from .entity import JebaoEntity


@dataclass(frozen=True, kw_only=True)
class JebaoBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a Jebao binary sensor."""

    is_on: Callable[[PumpStatus], bool]


def _fault(name: str) -> JebaoBinarySensorDescription:
    return JebaoBinarySensorDescription(
        key=f"fault_{name}",
        translation_key=f"fault_{name}",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on=lambda status: name in status.faults,
    )


DESCRIPTIONS: tuple[JebaoBinarySensorDescription, ...] = (
    JebaoBinarySensorDescription(
        key="feed_mode",
        translation_key="feed_mode",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on=lambda status: status.feed_switch,
    ),
    JebaoBinarySensorDescription(
        key="problem",
        translation_key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on=lambda status: bool(status.faults),
    ),
    # The app never uses this one; 0 = front-panel control, 1 = wireless control
    JebaoBinarySensorDescription(
        key="wireless_control",
        translation_key="wireless_control",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on=lambda status: status.wireless_mode,
    ),
    *(_fault(name) for name in FAULT_NAMES),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jebao binary sensors from config entry."""
    coordinator: JebaoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(JebaoBinarySensor(coordinator, description) for description in DESCRIPTIONS)


class JebaoBinarySensor(JebaoEntity, BinarySensorEntity):
    """A boolean datapoint of the pump."""

    entity_description: JebaoBinarySensorDescription

    def __init__(
        self,
        coordinator: JebaoDataUpdateCoordinator,
        description: JebaoBinarySensorDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the datapoint."""
        return self.entity_description.is_on(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """List the active faults on the summary sensor."""
        if self.entity_description.key == "problem":
            return {"faults": list(self.coordinator.data.faults)}
        return None
