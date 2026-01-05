"""Data update coordinator for Jebao."""
from datetime import timedelta
import logging
from typing import Optional

from jebao import JebaoError, MDP20000Device, discover_devices

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
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
        entry: ConfigEntry,
        device_id: str,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize coordinator."""
        self.device = device
        self.entry = entry
        self.device_id = device_id
        self._discovery_attempted = False

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from device."""
        try:
            # Check if connection is alive, reconnect if needed
            if not self.device.is_connected:
                _LOGGER.warning("Connection lost, attempting to reconnect...")
                try:
                    await self.device.connect(timeout=5.0)
                    _LOGGER.info("Reconnected successfully")
                    self._discovery_attempted = False  # Reset flag on successful reconnect
                except JebaoError as err:
                    _LOGGER.error("Reconnection failed: %s", err)

                    # Try discovery to find device with new IP
                    new_ip = await self._try_discovery_recovery()
                    if new_ip:
                        # Update device with new IP and reconnect
                        await self._reconnect_with_new_ip(new_ip)
                    else:
                        raise UpdateFailed(f"Failed to reconnect: {err}") from err

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

    async def _try_discovery_recovery(self) -> Optional[str]:
        """Try to find device via discovery if IP changed.

        Returns:
            New IP address if found, None otherwise
        """
        if self._discovery_attempted:
            _LOGGER.debug("Discovery already attempted this cycle, skipping")
            return None

        self._discovery_attempted = True
        current_ip = self.entry.data[CONF_HOST]

        _LOGGER.info("Attempting discovery to find device %s (current IP: %s)", self.device_id, current_ip)

        try:
            devices = await discover_devices(timeout=10.0)

            # Find our device by device_id
            for device in devices:
                if device.device_id == self.device_id:
                    if device.ip_address != current_ip:
                        _LOGGER.warning(
                            "Device %s found at new IP: %s (was: %s)",
                            self.device_id,
                            device.ip_address,
                            current_ip
                        )
                        return device.ip_address
                    else:
                        _LOGGER.info("Device found at same IP %s", current_ip)
                        return current_ip

            _LOGGER.error("Device %s not found in discovery", self.device_id)
            return None

        except Exception as err:
            _LOGGER.error("Discovery failed: %s", err)
            return None

    async def _reconnect_with_new_ip(self, new_ip: str) -> None:
        """Update config entry and reconnect with new IP.

        Args:
            new_ip: New IP address for the device

        Raises:
            JebaoError: If reconnection fails
        """
        current_ip = self.entry.data[CONF_HOST]

        # Update config entry with new IP
        _LOGGER.info("Updating config entry IP from %s to %s", current_ip, new_ip)
        new_data = dict(self.entry.data)
        new_data[CONF_HOST] = new_ip
        self.hass.config_entries.async_update_entry(self.entry, data=new_data)

        # Update device instance with new IP
        self.device.host = new_ip

        # Reconnect
        await self.device.disconnect()
        await self.device.connect(timeout=5.0)
        _LOGGER.info("Successfully reconnected to device at new IP %s", new_ip)
        self._discovery_attempted = False  # Reset flag on successful reconnect
