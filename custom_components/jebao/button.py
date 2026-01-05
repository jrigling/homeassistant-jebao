"""Button platform for Jebao."""
from __future__ import annotations

import logging

from jebao import JebaoError

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICE_ID, CONF_HOST, CONF_MODEL, DOMAIN
from .coordinator import JebaoDataUpdateCoordinator
from .entity import JebaoEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jebao buttons from config entry."""
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

    # Create buttons
    async_add_entities(
        [
            JebaoStartFeedButton(coordinator, device_id, model, host, device),
            JebaoCancelFeedButton(coordinator, device_id, model, host, device),
        ]
    )


class JebaoStartFeedButton(JebaoEntity, ButtonEntity):
    """Button to start feed mode."""

    _attr_translation_key = "start_feed"

    def __init__(
        self,
        coordinator: JebaoDataUpdateCoordinator,
        device_id: str,
        model: str,
        host: str,
        device,
    ) -> None:
        """Initialize button."""
        super().__init__(coordinator, device_id, model, host)
        self._device = device
        self._attr_unique_id = f"{device_id}_start_feed"
        self._attr_name = "Start feed"
        self._attr_icon = "mdi:fishbowl"

    async def async_press(self) -> None:
        """Handle button press."""
        try:
            # Get feed duration from number entity if available
            # Otherwise use default from device
            await self._device.start_feed()
            await self.coordinator.async_request_refresh()
            _LOGGER.info("Feed mode started")

        except JebaoError as err:
            _LOGGER.error("Failed to start feed mode: %s", err)


class JebaoCancelFeedButton(JebaoEntity, ButtonEntity):
    """Button to cancel feed mode."""

    _attr_translation_key = "cancel_feed"

    def __init__(
        self,
        coordinator: JebaoDataUpdateCoordinator,
        device_id: str,
        model: str,
        host: str,
        device,
    ) -> None:
        """Initialize button."""
        super().__init__(coordinator, device_id, model, host)
        self._device = device
        self._attr_unique_id = f"{device_id}_cancel_feed"
        self._attr_name = "Cancel feed"
        self._attr_icon = "mdi:cancel"

    async def async_press(self) -> None:
        """Handle button press."""
        try:
            await self._device.cancel_feed()
            await self.coordinator.async_request_refresh()
            _LOGGER.info("Feed mode canceled")

        except JebaoError as err:
            _LOGGER.error("Failed to cancel feed mode: %s", err)
