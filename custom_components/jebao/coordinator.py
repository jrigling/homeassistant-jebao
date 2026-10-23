"""Data update coordinator for Jebao."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from typing import Optional

from jebao import JebaoError, MDP20000Device, PumpStatus, discover_devices

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class JebaoDataUpdateCoordinator(DataUpdateCoordinator[PumpStatus]):
    """Polls one pump; data is its decoded status (every datapoint)."""

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
        # Polls and commands share one session; keep them from interleaving
        self._lock = asyncio.Lock()

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> PumpStatus:
        """Fetch data from device."""
        async with self._lock:
            try:
                await self._ensure_connected()
                await self.device.update()
            except JebaoError as err:
                # Start the next poll from a fresh session rather than a half-dead one
                await self.device.disconnect()
                raise UpdateFailed(f"Error communicating with device: {err}") from err

        status = self.device.status
        if status is None:
            raise UpdateFailed("Pump sent a status the integration couldn't decode")
        return status

    async def async_command(
        self, command: Callable[[MDP20000Device], Awaitable[None]]
    ) -> None:
        """Run a control command and publish the pump's new state.

        Raises:
            HomeAssistantError: The pump didn't take the command
        """
        async with self._lock:
            try:
                await self._ensure_connected()
                await command(self.device)
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err
            except JebaoError as err:
                await self.device.disconnect()
                raise HomeAssistantError(f"Pump command failed: {err}") from err
        # Writes return the pump's status report, so there's no need to poll
        if self.device.status is not None:
            self.async_set_updated_data(self.device.status)
        else:
            await self.async_request_refresh()

    async def async_sync_clock(self) -> None:
        """Set the pump's clock (which its schedule runs on) to HA's local time."""
        now = dt_util.now().replace(tzinfo=None)
        await self.async_command(lambda device: device.set_clock(now))

    async def _ensure_connected(self) -> None:
        if self.device.is_connected:
            return
        _LOGGER.debug("Connecting to %s", self.device.host)
        try:
            await self.device.connect(timeout=5.0)
            self._discovery_attempted = False
        except JebaoError as err:
            # Try discovery to find device with new IP
            new_ip = await self._try_discovery_recovery()
            if not new_ip:
                raise
            _LOGGER.debug("Reconnect to %s failed (%s), trying %s", self.device.host, err, new_ip)
            await self._reconnect_with_new_ip(new_ip)

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
                    _LOGGER.info("Device found at same IP %s", current_ip)
                    return current_ip

            _LOGGER.error("Device %s not found in discovery", self.device_id)
            return None

        except Exception as err:  # pylint: disable=broad-except
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
        self.device._protocol.host = new_ip  # pylint: disable=protected-access

        await self.device.disconnect()
        await self.device.connect(timeout=5.0)
        _LOGGER.info("Successfully reconnected to device at new IP %s", new_ip)
        self._discovery_attempted = False
