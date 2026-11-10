"""Data update coordinator for Jebao."""
from __future__ import annotations

from datetime import timedelta
import logging
import time
from typing import Any, Optional

from jebao import (
    JebaoConnectionError,
    JebaoError,
    JebaoTimeoutError,
    MDP20000Device,
    discover_devices,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# The pumps are on Wi-Fi and occasionally miss a poll. Keep the last known
# state for this many consecutive failed polls before going unavailable
# (3 x 30 s = 90 s with the default interval).
FAILURES_BEFORE_UNAVAILABLE = 3

# Minimum time between discovery-based IP recovery attempts while unreachable.
DISCOVERY_RECOVERY_INTERVAL = 300  # seconds


class JebaoDataUpdateCoordinator(DataUpdateCoordinator):
    """Polls one pump. Exactly one instance per config entry."""

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

    def _snapshot(self) -> dict[str, Any]:
        return {
            "state": self.device.state,
            "speed": self.device.speed,
            "is_on": self.device.is_on,
            "is_feed_mode": self.device.is_feed_mode,
            "is_program_mode": self.device.is_program_mode,
        }

    def _sync_host(self) -> None:
        """Follow IP changes written to the entry by DHCP / periodic discovery."""
        host = self.entry.data[CONF_HOST]
        if self.device.host != host:
            _LOGGER.info(
                "%s: using new IP %s (was %s)", self.entry.title, host, self.device.host
            )
            self.device.host = host

    async def _async_update_data(self) -> dict[str, Any]:
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
                    return self._snapshot()

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
        return self._snapshot()

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
