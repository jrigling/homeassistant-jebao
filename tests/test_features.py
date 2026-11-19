"""Schedule, clock, faults, speed setting, model option and pump identification."""
from datetime import datetime
from unittest.mock import patch

from jebao import DiscoveredDevice
from jebao.datapoints import encode_clock, encode_write
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.jebao.const import DOMAIN

from .test_init import DEVICE_ID, make_entry, setup

FLAGS = 8  # attribute flag bytes before the values in a write


def entity_id(hass, domain, key, device_id=DEVICE_ID):
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{device_id}_{key}")


async def test_entities_from_datapoints(hass: HomeAssistant, pump):
    await setup(hass, make_entry())
    # The fake pump reports FeedTime 1, speed 70, schedule off, no faults
    assert hass.states.get(entity_id(hass, "number", "feed_duration")).state == "1"
    assert hass.states.get(entity_id(hass, "number", "speed_setting")).state == "70"
    assert hass.states.get(entity_id(hass, "switch", "schedule")).state == "off"
    assert hass.states.get(entity_id(hass, "binary_sensor", "problem")).state == "off"


async def test_speed_setting_uses_pump_units(hass: HomeAssistant, pump):
    await setup(hass, make_entry())
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": entity_id(hass, "number", "speed_setting"), "value": 30},
        blocking=True,
    )
    assert pump.commands == [bytes([0x20, 0, 30, 0])]


async def test_feed_duration_writes_feed_time(hass: HomeAssistant, pump):
    await setup(hass, make_entry())
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": entity_id(hass, "number", "feed_duration"), "value": 15},
        blocking=True,
    )
    assert pump.writes == [encode_write({"feed_time": 15, "feed_switch": False})]


async def test_schedule_switch_and_service(hass: HomeAssistant, pump):
    await setup(hass, make_entry())
    switch = entity_id(hass, "switch", "schedule")
    await hass.services.async_call(
        DOMAIN, "set_schedule",
        {
            "entity_id": switch,
            "slots": [{"start": "08:00", "end": "20:00", "speed": 60}],
            "enable": True,
        },
        blocking=True,
    )
    schedule, enable = pump.writes
    # Slot 0 (id 11) is flagged, and holds 08:00-20:00 run at 60%
    assert schedule[FLAGS + 13 : FLAGS + 19] == bytes((8, 0, 20, 0, 1, 60))
    assert enable[7] & 0x08  # TimerON flagged...
    assert enable[FLAGS] & 0x08  # ...and set

    pump.writes.clear()
    await hass.services.async_call("switch", "turn_off", {"entity_id": switch}, blocking=True)
    assert pump.writes == [encode_write({"timer_on": False, "motor_speed": 70})]


async def test_clock_synced_at_startup_and_on_demand(hass: HomeAssistant, pump):
    await setup(hass, make_entry(sync_clock=True))
    assert len(pump.writes) == 1
    flags = encode_write(encode_clock(datetime(2026, 1, 1)))[:FLAGS]
    assert pump.writes[0][:FLAGS] == flags

    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id(hass, "button", "sync_clock")}, blocking=True
    )
    assert len(pump.writes) == 2 and pump.writes[1][:FLAGS] == flags


async def test_entry_added_by_ip_gets_the_pump_id(hass: HomeAssistant, pump):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="unknown",
        title="MDP-20000 (127.0.0.1)",
        data={CONF_HOST: "127.0.0.1", "device_id": "unknown", "model": "MDP-20000"},
        options={"sync_clock": False},
    )
    entry.add_to_hass(hass)
    # An entity registered under the placeholder ID, as older versions created it
    old = er.async_get(hass).async_get_or_create(
        "fan", DOMAIN, "unknown_fan", config_entry=entry
    )
    found = DiscoveredDevice(
        device_id=DEVICE_ID,
        mac_address="44:17:93:2a:5c:5f",
        product_key="6a5c47b3ea364ecb841b47f5997a1775",
        ip_address="127.0.0.1",
        model="MDP-20000",
        firmware_version="04D30Q34",
    )
    with patch("custom_components.jebao.query_device", return_value=found):
        await setup(hass, entry)
    assert entry.unique_id == DEVICE_ID
    assert entry.data["device_id"] == DEVICE_ID
    # Same entity (history kept), now under the real ID
    assert er.async_get(hass).async_get(old.entity_id).unique_id == f"{DEVICE_ID}_fan"


async def test_model_option_names_the_device(hass: HomeAssistant, pump):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE_ID,
        title="MDP-20000 (127.0.0.1)",
        data={CONF_HOST: "127.0.0.1", "device_id": DEVICE_ID, "model": "MDP-20000"},
        options={"sync_clock": False},
    )
    await setup(hass, entry)
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "model": "MDP-15000"}
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.title == "MDP-15000 (127.0.0.1)"
    from homeassistant.helpers import device_registry as dr

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, DEVICE_ID)})
    assert device.model == "MDP-15000"
