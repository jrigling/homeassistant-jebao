"""Config flow for Jebao integration."""
from __future__ import annotations

import logging
from typing import Any

import netifaces
import voluptuous as vol
from jebao import JebaoError, MDP20000Device, discover_devices

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_DEVICE_ID,
    CONF_INTERFACES,
    CONF_MODEL,
    DEFAULT_NAME,
    DOMAIN,
    MODEL_MDP20000,
)

_LOGGER = logging.getLogger(__name__)


async def validate_connection(hass: HomeAssistant, host: str) -> dict[str, Any]:
    """Validate we can connect to the device.

    Returns:
        Dict with device info on success

    Raises:
        JebaoError: Connection or authentication failed
    """
    device = MDP20000Device(host=host)

    try:
        await device.connect(timeout=10.0)
        await device.update()

        # Get device info
        info = {
            "device_id": device.device_id or "unknown",
            "model": device.model or MODEL_MDP20000,
            "state": device.state.name if device.state else "unknown",
        }

        return info

    finally:
        await device.disconnect()


class JebaoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Jebao."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._discovered_devices: dict[str, Any] = {}
        self._selected_interfaces: list[str] | None = None
        self._discovery_attempted: bool = False
        self._no_devices_reason: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - choose discovery method."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["discover", "manual"],
        )

    async def async_step_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle discovery step - select interfaces."""
        errors = {}

        if user_input is not None:
            # User selected interfaces, proceed with discovery
            # Extract just the interface names (strip IP addresses in parentheses)
            selected = user_input.get(CONF_INTERFACES, [])
            self._selected_interfaces = [
                iface.split(" (")[0] for iface in selected
            ]
            _LOGGER.debug(
                "User selected interfaces: %s -> parsed as: %s",
                selected,
                self._selected_interfaces,
            )
            return await self.async_step_select_device()

        # Get available network interfaces
        interfaces = self._get_available_interfaces()

        if not interfaces:
            return await self.async_step_manual()

        # Show interface selection form
        return self.async_show_form(
            step_id="discover",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_INTERFACES,
                        default=interfaces,  # All selected by default
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=interfaces,
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            description_placeholders={
                "interface_count": str(len(interfaces)),
                "interfaces": ", ".join(interfaces),
            },
            errors=errors,
        )

    async def async_step_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle device selection after discovery."""
        errors = {}

        if user_input is not None:
            # User selected a device
            selected_id = user_input["device"]
            device_info = self._discovered_devices[selected_id]

            # Check if already configured
            await self.async_set_unique_id(device_info["device_id"])
            self._abort_if_unique_id_configured()

            # Create entry
            return self.async_create_entry(
                title=f"{device_info['model']} ({device_info['ip']})",
                data={
                    CONF_HOST: device_info["ip"],
                    CONF_DEVICE_ID: device_info["device_id"],
                    CONF_MODEL: device_info["model"],
                },
            )

        # Perform discovery
        _LOGGER.info(
            "Starting discovery on interfaces: %s", self._selected_interfaces
        )

        try:
            devices = await discover_devices(
                timeout=10.0, interfaces=self._selected_interfaces
            )
            _LOGGER.info("Discovery completed, found %d device(s)", len(devices))
        except Exception as err:
            _LOGGER.error("Discovery failed: %s", err, exc_info=True)
            errors["base"] = "discovery_failed"
            return self.async_show_form(
                step_id="select_device",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        if not devices:
            _LOGGER.warning(
                "No devices found during discovery on interfaces: %s",
                self._selected_interfaces
            )
            self._discovery_attempted = True
            self._no_devices_reason = "no_devices"
            return await self.async_step_manual()

        # Filter to MDP-20000 devices (MD-4.4 support can be added later)
        mdp_devices = [d for d in devices if d.is_mdp20000]

        if not mdp_devices:
            _LOGGER.warning("No MDP-20000 devices found")
            self._discovery_attempted = True
            self._no_devices_reason = "no_mdp20000"
            return await self.async_step_manual()

        # Store discovered devices
        self._discovered_devices = {
            f"{d.device_id}_{d.ip_address}": {
                "device_id": d.device_id,
                "ip": d.ip_address,
                "model": d.model,
                "mac": d.mac_address,
            }
            for d in mdp_devices
        }

        # Show device selection
        device_options = [
            selector.SelectOptionDict(
                value=key,
                label=f"{info['model']} ({info['device_id']}) at {info['ip']}",
            )
            for key, info in self._discovered_devices.items()
        ]

        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema(
                {
                    vol.Required("device"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=device_options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            description_placeholders={
                "device_count": str(len(mdp_devices)),
            },
            errors=errors,
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual configuration."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            try:
                # Validate connection
                info = await validate_connection(self.hass, host)

                # Check if already configured
                await self.async_set_unique_id(info["device_id"])
                self._abort_if_unique_id_configured()

                # Create entry
                return self.async_create_entry(
                    title=f"{info['model']} ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_DEVICE_ID: info["device_id"],
                        CONF_MODEL: info["model"],
                    },
                )

            except JebaoError as err:
                _LOGGER.error("Failed to connect to %s: %s", host, err)
                errors["base"] = "cannot_connect"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error: %s", err)
                errors["base"] = "unknown"

        # Prepare description placeholders based on discovery context
        description_placeholders = {}
        if self._discovery_attempted:
            if self._no_devices_reason == "no_devices":
                description_placeholders["discovery_result"] = (
                    "⚠️ No Jebao pumps were found during automatic discovery."
                )
            elif self._no_devices_reason == "no_mdp20000":
                description_placeholders["discovery_result"] = (
                    "⚠️ No MDP-20000 pumps were found during automatic discovery. "
                    "Other Jebao models may not be supported yet."
                )
            else:
                description_placeholders["discovery_result"] = (
                    "⚠️ Automatic discovery did not find any pumps."
                )
        else:
            description_placeholders["discovery_result"] = ""

        # Show manual configuration form
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                }
            ),
            description_placeholders=description_placeholders,
            errors=errors,
        )

    @staticmethod
    def _get_available_interfaces() -> list[str]:
        """Get available network interfaces.

        Returns:
            List of interface names that have IPv4 addresses
        """
        interfaces = []

        try:
            for iface in netifaces.interfaces():
                # Skip loopback
                if iface.startswith("lo"):
                    continue

                # Check if interface has IPv4 address
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    # Get IP to show in description
                    ip = addrs[netifaces.AF_INET][0]["addr"]
                    interfaces.append(f"{iface} ({ip})")

        except Exception as err:
            _LOGGER.error("Error enumerating interfaces: %s", err)

        return interfaces

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> JebaoOptionsFlow:
        """Get options flow handler."""
        return JebaoOptionsFlow(config_entry)


class JebaoOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Jebao."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        from .const import DEFAULT_SCAN_INTERVAL

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "scan_interval",
                        default=self.config_entry.options.get(
                            "scan_interval", DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                }
            ),
        )
