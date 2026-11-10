"""Fixtures for Jebao integration tests."""
import sys
import types

# The newest HA test harness that installs on Python 3.12 is 2025.1, which
# predates homeassistant.helpers.service_info.dhcp (2025.2). Shim it there.
try:  # pragma: no cover
    import homeassistant.helpers.service_info.dhcp  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    from dataclasses import dataclass

    @dataclass(slots=True)
    class DhcpServiceInfo:  # same fields as HA's
        ip: str
        hostname: str
        macaddress: str

    _mod = types.ModuleType("homeassistant.helpers.service_info.dhcp")
    _mod.DhcpServiceInfo = DhcpServiceInfo
    sys.modules[_mod.__name__] = _mod
from unittest.mock import patch

import pytest

from jebao import MDP20000Device

from .fake_pump import FakePump


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    yield


@pytest.fixture(autouse=True)
def no_real_discovery():
    """Keep the background UDP scan off the real network during tests."""
    with patch("custom_components.jebao.discover_devices", return_value=[]), patch(
        "custom_components.jebao.coordinator.discover_devices", return_value=[]
    ):
        yield


@pytest.fixture
async def pump(socket_enabled):
    p = FakePump()
    await p.start()
    with patch(
        "custom_components.jebao.MDP20000Device",
        lambda host, device_id=None, **kw: MDP20000Device(
            host, port=p.port, device_id=device_id, **kw
        ),
    ):
        yield p
    await p.stop()
