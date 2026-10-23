"""Button platform for Jebao."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import JebaoDataUpdateCoordinator
from .entity import JebaoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jebao buttons from config entry."""
    coordinator: JebaoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        [
            JebaoStartFeedButton(coordinator),
            JebaoCancelFeedButton(coordinator),
            JebaoSyncClockButton(coordinator),
        ]
    )


class JebaoStartFeedButton(JebaoEntity, ButtonEntity):
    """Pause the pump for the feed duration (turns the schedule off, as the app does)."""

    _attr_translation_key = "start_feed"
    _attr_icon = "mdi:fishbowl"

    def __init__(self, coordinator: JebaoDataUpdateCoordinator) -> None:
        """Initialize button."""
        super().__init__(coordinator, "start_feed")

    async def async_press(self) -> None:
        """Handle button press."""
        await self.coordinator.async_command(lambda device: device.start_feed())


class JebaoCancelFeedButton(JebaoEntity, ButtonEntity):
    """End feed mode early."""

    _attr_translation_key = "cancel_feed"
    _attr_icon = "mdi:cancel"

    def __init__(self, coordinator: JebaoDataUpdateCoordinator) -> None:
        """Initialize button."""
        super().__init__(coordinator, "cancel_feed")

    async def async_press(self) -> None:
        """Handle button press."""
        await self.coordinator.async_command(lambda device: device.cancel_feed())


class JebaoSyncClockButton(JebaoEntity, ButtonEntity):
    """Set the pump's clock, which its schedule runs on, to Home Assistant's time."""

    _attr_translation_key = "sync_clock"
    _attr_icon = "mdi:clock-check-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: JebaoDataUpdateCoordinator) -> None:
        """Initialize button."""
        super().__init__(coordinator, "sync_clock")

    async def async_press(self) -> None:
        """Handle button press."""
        await self.coordinator.async_sync_clock()
