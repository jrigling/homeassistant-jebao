"""The Jebao integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from jebao import JebaoError, MDP20000Device, discover_devices

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import CONF_DEVICE_ID, CONF_MODEL, DOMAIN, MODEL_MDP20000, SELECTABLE_MODELS
from .coordinator import JebaoDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.FAN,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
]

# Periodic background discovery interval (UDP broadcast scan)
DISCOVERY_INTERVAL = timedelta(minutes=5)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up periodic background discovery for Jebao pumps."""

    async def _periodic_discovery(_now=None) -> None:
        try:
            devices = await discover_devices(timeout=5.0)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.debug("Periodic discovery failed: %s", err)
            return

        entries = hass.config_entries.async_entries(DOMAIN)
        entries_by_id = {entry.unique_id: entry for entry in entries}
        # Entries added by IP before the pump's ID could be looked up
        entries_by_host = {
            entry.data.get(CONF_HOST): entry
            for entry in entries
            if entry.data.get(CONF_DEVICE_ID) in (None, "unknown")
        }

        for device in devices:
            if not device.is_mdp20000:
                continue

            existing = entries_by_id.get(device.device_id) or entries_by_host.get(
                device.ip_address
            )
            if existing is not None:
                # Backfill missing MAC / update IP if it drifted (DHCP discovery is the
                # preferred IP-recovery path, but periodic scan is a belt-and-suspenders).
                updates: dict[str, Any] = {}
                if not existing.data.get("mac_address") and device.mac_address:
                    updates["mac_address"] = device.mac_address
                if existing.data.get(CONF_HOST) != device.ip_address:
                    updates[CONF_HOST] = device.ip_address
                if device.model and existing.data.get(CONF_MODEL) != device.model:
                    updates[CONF_MODEL] = device.model
                if updates:
                    _LOGGER.info(
                        "Updating Jebao entry %s from periodic discovery: %s",
                        existing.title,
                        updates,
                    )
                    # The update listener reloads the entry, so names follow the model
                    hass.config_entries.async_update_entry(
                        existing, data={**existing.data, **updates}
                    )
                continue

            # New, unconfigured pump - kick off a discovery flow so it appears
            # in Settings -> Devices & Services as "Discovered".
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": SOURCE_INTEGRATION_DISCOVERY},
                    data={
                        "device_id": device.device_id,
                        "ip": device.ip_address,
                        "model": device.model,
                        "mac_address": device.mac_address,
                        "firmware_version": device.firmware_version,
                    },
                )
            )

    # Fire once shortly after startup, then on the regular interval.
    hass.async_create_background_task(
        _periodic_discovery(), "jebao_initial_discovery"
    )
    async_track_time_interval(hass, _periodic_discovery, DISCOVERY_INTERVAL)
    return True


def entry_model(entry: ConfigEntry) -> str:
    """Return the entry's model: the user's choice in options, else discovery's."""
    return entry.options.get(CONF_MODEL) or entry.data.get(CONF_MODEL, MODEL_MDP20000)


async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options or discovered data change, so names and settings apply."""
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if data is not None and data["entry_snapshot"] == (dict(entry.data), dict(entry.options)):
        return  # Title-only change (e.g. setup renaming it); nothing to apply
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Jebao from a config entry."""
    host = entry.data[CONF_HOST]
    device_id = entry.data.get("device_id")
    model = entry_model(entry)
    mac_address = entry.data.get("mac_address")
    firmware_version = entry.data.get("firmware_version")

    _LOGGER.info("Setting up Jebao device at %s", host)

    # Create device instance
    device = MDP20000Device(host=host, device_id=device_id)

    try:
        # Connect to device
        await device.connect()

        # Ensure manual mode (exit Program mode if active)
        await device.ensure_manual_mode()

        _LOGGER.info("Successfully connected to Jebao device at %s", host)

    except JebaoError as err:
        _LOGGER.error("Failed to connect to Jebao device at %s: %s", host, err)
        await device.disconnect()
        raise ConfigEntryNotReady(f"Failed to connect: {err}") from err

    # One coordinator per entry, shared by all platforms. Platforms used to each
    # create their own (they set up concurrently, so the "if not in data" check
    # raced), which polled the pump several times per interval and, when the
    # connection dropped, sent several simultaneous logins that pumps reject.
    scan_interval = entry.options.get("scan_interval")
    if scan_interval:
        coordinator = JebaoDataUpdateCoordinator(hass, device, entry, device_id, scan_interval)
    else:
        coordinator = JebaoDataUpdateCoordinator(hass, device, entry, device_id)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await device.disconnect()
        raise

    # Store device instance
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "device": device,
        "host": host,
        "device_id": device_id,
        "model": model,
        "mac_address": mac_address,
        "firmware_version": firmware_version,
        "coordinator": coordinator,
        # What this setup was built from, so the update listener can skip reloads
        "entry_snapshot": (dict(entry.data), dict(entry.options)),
    }

    # Keep a "<model> (<ip>)" title in step with the model (before the listener,
    # so this doesn't trigger a reload)
    for known in SELECTABLE_MODELS:
        if known != model and entry.title.startswith(f"{known} "):
            hass.config_entries.async_update_entry(
                entry, title=model + entry.title[len(known):]
            )
            break

    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Disconnect device
        data = hass.data[DOMAIN].pop(entry.entry_id)
        device: MDP20000Device = data["device"]
        await device.disconnect()
        _LOGGER.info("Disconnected from Jebao device at %s", data["host"])

    return unload_ok


def get_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Get device info for device registry."""
    device_id = entry.data.get("device_id", "unknown")
    model = entry_model(entry)
    host = entry.data[CONF_HOST]

    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=entry.title,
        manufacturer="Jebao",
        model=model,
        configuration_url=f"http://{host}:12416",
    )
