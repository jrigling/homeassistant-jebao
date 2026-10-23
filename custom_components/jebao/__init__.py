"""The Jebao integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from jebao import JebaoError, MDP20000Device, discover_devices, query_device

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_time_change, async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DEVICE_ID,
    CONF_MODEL,
    CONF_SCAN_INTERVAL,
    CONF_SYNC_CLOCK,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SYNC_CLOCK,
    DOMAIN,
    MODEL_MDP20000,
    SELECTABLE_MODELS,
)
from .coordinator import JebaoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.FAN,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Periodic background discovery interval (UDP broadcast scan)
DISCOVERY_INTERVAL = timedelta(minutes=5)

# Daily clock sync, after any DST change (the pump's schedule runs on its own clock,
# which nothing else sets)
CLOCK_SYNC_TIME = {"hour": 3, "minute": 17, "second": 0}

UNKNOWN_DEVICE_ID = "unknown"


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
            if entry.data.get(CONF_DEVICE_ID) in (None, UNKNOWN_DEVICE_ID)
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
                if device.firmware_version and existing.data.get("firmware_version") != device.firmware_version:
                    updates["firmware_version"] = device.firmware_version
                if existing.data.get(CONF_DEVICE_ID) in (None, UNKNOWN_DEVICE_ID):
                    # Picked up on the reload the update below triggers
                    updates[CONF_DEVICE_ID] = device.device_id
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


async def _async_identify(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Fill in the pump's ID (and MAC/firmware) for an entry added by IP.

    Such entries were stored with device ID "unknown", which their unique ID and
    every entity's unique ID were built from. Ask the pump directly and move them
    all over to its real ID, keeping entity IDs and history.
    """
    if entry.data.get(CONF_DEVICE_ID) not in (None, UNKNOWN_DEVICE_ID):
        if entry.unique_id in (None, UNKNOWN_DEVICE_ID):
            # The ID came from periodic discovery; finish the move
            _async_adopt_device_id(hass, entry, entry.data[CONF_DEVICE_ID])
        return
    found = await query_device(entry.data[CONF_HOST])
    if found is None or not found.device_id:
        _LOGGER.debug("Couldn't look up the ID of the pump at %s", entry.data[CONF_HOST])
        return
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            CONF_DEVICE_ID: found.device_id,
            "mac_address": entry.data.get("mac_address") or found.mac_address,
            "firmware_version": found.firmware_version,
        },
    )
    _async_adopt_device_id(hass, entry, found.device_id)


@callback
def _async_adopt_device_id(hass: HomeAssistant, entry: ConfigEntry, device_id: str) -> None:
    old_prefix = f"{UNKNOWN_DEVICE_ID}_"
    ent_reg = er.async_get(hass)
    for ent in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if ent.unique_id.startswith(old_prefix):
            new_unique_id = device_id + ent.unique_id[len(UNKNOWN_DEVICE_ID):]
            if ent_reg.async_get_entity_id(ent.domain, DOMAIN, new_unique_id) is None:
                ent_reg.async_update_entity(ent.entity_id, new_unique_id=new_unique_id)
    dev_reg = dr.async_get(hass)
    for dev in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        if (DOMAIN, UNKNOWN_DEVICE_ID) in dev.identifiers:
            dev_reg.async_update_device(dev.id, new_identifiers={(DOMAIN, device_id)})
    if not any(
        other.unique_id == device_id
        for other in hass.config_entries.async_entries(DOMAIN)
        if other.entry_id != entry.entry_id
    ):
        hass.config_entries.async_update_entry(entry, unique_id=device_id)
    _LOGGER.info("Pump at %s identified as %s", entry.data[CONF_HOST], device_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Jebao from a config entry."""
    await _async_identify(hass, entry)

    host = entry.data[CONF_HOST]
    device_id = entry.data.get(CONF_DEVICE_ID) or UNKNOWN_DEVICE_ID
    model = entry_model(entry)

    _LOGGER.info("Setting up Jebao device at %s", host)

    device = MDP20000Device(host=host, device_id=device_id)
    try:
        # Connecting also reads the status. The pump is left in whatever mode it's
        # in: older versions forced it out of its schedule on every start.
        await device.connect()
    except JebaoError as err:
        await device.disconnect()
        raise ConfigEntryNotReady(f"Failed to connect to {host}: {err}") from err

    # One coordinator per entry, shared by all platforms. Platforms used to each
    # create their own (they set up concurrently, so the "if not in data" check
    # raced), which polled the pump several times per interval and, when the
    # connection dropped, sent several simultaneous logins that pumps reject.
    coordinator = JebaoDataUpdateCoordinator(
        hass,
        device,
        entry,
        device_id,
        entry.options.get(CONF_SCAN_INTERVAL) or DEFAULT_SCAN_INTERVAL,
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await device.disconnect()
        raise

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "device": device,
        "host": host,
        "device_id": device_id,
        "model": model,
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

    if entry.options.get(CONF_SYNC_CLOCK, DEFAULT_SYNC_CLOCK):

        async def _sync_clock(_now=None) -> None:
            try:
                await coordinator.async_sync_clock()
            except HomeAssistantError as err:
                _LOGGER.warning("Couldn't set the clock of %s: %s", entry.title, err)

        entry.async_on_unload(async_track_time_change(hass, _sync_clock, **CLOCK_SYNC_TIME))
        entry.async_create_background_task(hass, _sync_clock(), f"jebao_clock_{entry.entry_id}")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        device: MDP20000Device = data["device"]
        await device.disconnect()
        _LOGGER.info("Disconnected from Jebao device at %s", data["host"])

    return unload_ok
