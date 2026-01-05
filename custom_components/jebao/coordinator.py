"""Data update coordinator for Jebao."""
from datetime import timedelta
import logging

from jebao import JebaoError, MDP20000Device

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class JebaoDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Jebao data."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: MDP20000Device,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize coordinator."""
        self.device = device

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from device."""
        try:
            await self.device.update()

            return {
                "state": self.device.state,
                "speed": self.device.speed,
                "is_on": self.device.is_on,
                "is_feed_mode": self.device.is_feed_mode,
                "is_program_mode": self.device.is_program_mode,
            }

        except JebaoError as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err
