"""Data update coordinator for Jebao."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
import time
from typing import Optional

from jebao import (
    JebaoConnectionError,
    JebaoError,
    JebaoTimeoutError,
    MDP20000Device,
    PumpStatus,
    discover_devices,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_PASSCODE, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# The pumps are on Wi-Fi and occasionally miss a poll. Keep the last known
# state for this many consecutive failed polls before going unavailable
# (3 x 30 s = 90 s with the default interval).
FAILURES_BEFORE_UNAVAILABLE = 3

# Minimum time between discovery-based IP recovery attempts while unreachable.
DISCOVERY_RECOVERY_INTERVAL = 300  # seconds


class JebaoDataUpdateCoordinator(DataUpdateCoordinator[PumpStatus]):
    """Polls one pump; data is its decoded status (every datapoint).

    Exactly one instance per config entry.
    """

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
        self._consecutive_failures = 0
        self._last_discovery = 0.0

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(seconds=scan_interval),
        )

    def _status(self) -> PumpStatus:
        self._save_passcode()
        status = self.device.status
        if status is None:
            raise UpdateFailed("Pump sent a status the integration couldn't decode")
        return status

    def _save_passcode(self) -> None:
        """Keep the pump's passcode so HA can log in after its binding window."""
        passcode = self.device.passcode
        if passcode and self.entry.data.get(CONF_PASSCODE) != passcode.hex():
            self.hass.config_entries.async_update_entry(
                self.entry, data={**self.entry.data, CONF_PASSCODE: passcode.hex()}
            )

    def _sync_host(self) -> None:
        """Follow IP changes written to the entry by DHCP / periodic discovery."""
        host = self.entry.data[CONF_HOST]
        if self.device.host != host:
            _LOGGER.info(
                "%s: using new IP %s (was %s)", self.entry.title, host, self.device.host
            )
            self.device.host = host

    async def _async_update_data(self) -> PumpStatus:
        """Fetch data from device."""
        self._sync_host()
        try:
            await self.device.update()
        except JebaoError as err:
            if isinstance(err, (JebaoConnectionError, JebaoTimeoutError)) and (
                await self._try_discovery_recovery()
            ):
                try:
                    await self.device.update()
                except JebaoError as retry_err:
                    err = retry_err
                else:
                    self._consecutive_failures = 0
                    return self._status()

            self._consecutive_failures += 1
            if (
                self.data is not None
                and self._consecutive_failures < FAILURES_BEFORE_UNAVAILABLE
            ):
                _LOGGER.debug(
                    "%s: poll failed (%d/%d), keeping last state: %s",
                    self.entry.title,
                    self._consecutive_failures,
                    FAILURES_BEFORE_UNAVAILABLE,
                    err,
                )
                return self.data
            raise UpdateFailed(f"Error communicating with pump: {err}") from err

        self._consecutive_failures = 0
        return self._status()

    async def async_command(
        self, command: Callable[[MDP20000Device], Awaitable[None]]
    ) -> None:
        """Run a control command and publish the pump's new state.

        Raises:
            HomeAssistantError: The pump didn't take the command
        """
        self._sync_host()
        try:
            await command(self.device)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        except JebaoError as err:
            raise HomeAssistantError(f"Pump command failed: {err}") from err
        # Read the result straight away (the new value reads back at once).
        # Publishing also restarts the poll timer, so publishing the status from
        # before the command would hide the change for a whole interval.
        try:
            await self.device.update()
        except JebaoError as err:
            # The pump took the command, so don't report it as failed
            _LOGGER.debug("Read-back from %s failed: %s", self.entry.title, err)
            await self.async_request_refresh()
            return
        self._consecutive_failures = 0
        self.async_set_updated_data(self._status())

    async def async_sync_clock(self) -> None:
        """Set the pump's clock (which its schedule runs on) to HA's local time."""
        now = dt_util.now().replace(tzinfo=None)
        await self.async_command(lambda device: device.set_clock(now))

    async def _try_discovery_recovery(self) -> bool:
        """If the pump moved to a new IP, point at it. Returns True if the IP changed."""
        # Only after the pump has been missing for a bit, and rate-limited.
        if self._consecutive_failures < 1:
            return False
        now = time.monotonic()
        if now - self._last_discovery < DISCOVERY_RECOVERY_INTERVAL:
            return False
        self._last_discovery = now

        try:
            devices = await discover_devices(timeout=3.0)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Discovery failed: %s", err)
            return False

        new_ip: Optional[str] = next(
            (d.ip_address for d in devices if d.device_id == self.device_id), None
        )
        if new_ip is None:
            _LOGGER.debug("%s: not found by discovery", self.entry.title)
            return False
        if new_ip == self.device.host:
            return False

        _LOGGER.warning(
            "%s: found at new IP %s (was %s)", self.entry.title, new_ip, self.device.host
        )
        self.hass.config_entries.async_update_entry(
            self.entry, data={**self.entry.data, CONF_HOST: new_ip}
        )
        self.device.host = new_ip
        return True
