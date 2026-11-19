"""Integration tests: real component inside HA, talking to a fake pump."""
from datetime import timedelta
import os

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from custom_components.jebao.const import DOMAIN

DEVICE_ID = "t4RoEiuukqgYeC8hwF7QUS"


def make_entry(host="127.0.0.1", sync_clock=False):
    # Clock sync off by default here: it writes to the pump at startup, which
    # the tests that count commands don't expect (see test_features.py)
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE_ID,
        title="Wetland pump 1",
        data={CONF_HOST: host, "device_id": DEVICE_ID, "model": "MDP-20000"},
        options={"sync_clock": sync_clock},
    )


async def setup(hass, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED


def fan_state(hass):
    states = hass.states.async_all("fan")
    assert len(states) == 1
    return states[0]


async def tick(hass, seconds=31):
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_single_coordinator_one_session_per_poll(hass: HomeAssistant, pump):
    entry = make_entry()
    await setup(hass, entry)
    assert fan_state(hass).state == "on"
    # All 5 platforms share one coordinator
    coords = {id(e.coordinator) for e in hass.data["entity_components"]["fan"].entities}
    assert len(coords) == 1

    before = pump.connections
    now = dt_util.utcnow()
    for i in range(1, 5):
        async_fire_time_changed(hass, now + timedelta(seconds=31 * i))
        await hass.async_block_till_done(wait_background_tasks=True)
    # 4 polls -> 4 sessions (pre-fix: up to 5 coordinators each polling)
    assert pump.connections - before == 4


async def test_brief_outage_keeps_state_then_goes_unavailable(hass: HomeAssistant, pump):
    entry = make_entry()
    await setup(hass, entry)
    now = dt_util.utcnow()

    # Each failed poll = 3 refused sessions (library retries internally).
    pump.faults = ["refuse"] * 3
    async_fire_time_changed(hass, now + timedelta(seconds=31))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert fan_state(hass).state == "on"  # 1 miss: still available

    pump.faults = ["refuse"] * 6
    async_fire_time_changed(hass, now + timedelta(seconds=62))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert fan_state(hass).state == "on"  # 2 misses: still available
    async_fire_time_changed(hass, now + timedelta(seconds=93))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert fan_state(hass).state == STATE_UNAVAILABLE  # 3 misses

    async_fire_time_changed(hass, now + timedelta(seconds=124))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert fan_state(hass).state == "on"  # recovers


async def test_setup_retries_then_follows_host_change(hass: HomeAssistant, pump):
    # Pump unreachable at setup -> SETUP_RETRY (not an error), then loads.
    pump.faults = ["refuse"] * 3
    entry = make_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED

    # While loaded, a host written to entry.data (by DHCP / periodic
    # discovery) is used by the very next poll - no restart needed.
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coordinator.device.host = "192.0.2.1"  # stale IP the device object was using
    hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_HOST: "127.0.0.1"})
    await coordinator.async_refresh()
    assert coordinator.device.host == "127.0.0.1"
    assert coordinator.last_update_success


async def test_command_failure_raises(hass: HomeAssistant, pump):
    entry = make_entry()
    await setup(hass, entry)
    pump.faults = ["refuse", "refuse"]
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "fan", "turn_off", {"entity_id": fan_state(hass).entity_id}, blocking=True
        )
    assert pump.commands == []


async def test_set_speed_command(hass: HomeAssistant, pump):
    entry = make_entry()
    await setup(hass, entry)
    await hass.services.async_call(
        "fan", "set_percentage",
        {"entity_id": fan_state(hass).entity_id, "percentage": 100},
        blocking=True,
    )
    assert pump.commands == [bytes([0x20, 0, 100, 0])]


@pytest.mark.skipif(not os.environ.get("JEBAO_LIVE_HOST"), reason="set JEBAO_LIVE_HOST to run")
async def test_live_pump_read_only(hass: HomeAssistant, socket_enabled):
    """Against real hardware: setup + polls. Sends no control commands."""
    import pytest_socket

    host = os.environ["JEBAO_LIVE_HOST"]
    pytest_socket.socket_allow_hosts(["127.0.0.1", host])
    entry = make_entry(host=host)
    await setup(hass, entry)
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    for _ in range(int(os.environ.get("JEBAO_LIVE_POLLS", "5"))):
        await coordinator.async_refresh()
        assert coordinator.last_update_success
        assert coordinator._consecutive_failures == 0
    assert fan_state(hass).state in ("on", "off")


async def test_passcode_and_source_port_saved(hass: HomeAssistant, pump):
    entry = make_entry()
    other = MockConfigEntry(domain=DOMAIN, unique_id="other", data={CONF_HOST: "192.0.2.9"})
    other.add_to_hass(hass)
    await setup(hass, entry)
    assert entry.data["passcode"] == b"ABCDEFGHIJ".hex()
    port = entry.data["local_port"]
    assert 21000 <= port < 25000
    assert set(pump.peer_ports) == {port}

    # After a restart the saved passcode is used: the pump isn't asked again,
    # which matters once its post-power-up binding window has closed.
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED
    assert pump.passcode_requests == 1
    assert entry.data["local_port"] == port


async def test_setup_leaves_pump_schedule_alone(hass: HomeAssistant, pump):
    pump.state = 0x18  # running its own schedule, currently in a stopped slot
    entry = make_entry()
    await setup(hass, entry)
    assert pump.commands == []  # pre-0.2.1: EXIT_PROGRAM on every HA start
    assert fan_state(hass).state == "off"
    pump.state = 0x19  # schedule moves to a running slot
    await tick(hass)
    assert fan_state(hass).state == "on"
