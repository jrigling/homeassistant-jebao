"""Base entity for Jebao integration."""
from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import JebaoDataUpdateCoordinator


class JebaoEntity(CoordinatorEntity[JebaoDataUpdateCoordinator]):
    """Base entity for Jebao devices.

    Unique IDs are "<device_id>_<key>", the scheme older versions used, so existing
    entities keep their IDs and history.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: JebaoDataUpdateCoordinator, key: str) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        entry = coordinator.entry
        device_id = coordinator.device_id
        self._attr_unique_id = f"{device_id}_{key}"

        # Imported here: __init__ imports the platforms' base classes
        from . import entry_model  # pylint: disable=import-outside-toplevel

        model = entry_model(entry)
        device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            # The entry title, so pumps of the same model can be told apart
            name=entry.title,
            manufacturer="Jebao",
            model=model,
            serial_number=device_id,
        )
        if mac := entry.data.get("mac_address"):
            device_info["connections"] = {(CONNECTION_NETWORK_MAC, mac)}
        if firmware := entry.data.get("firmware_version"):
            device_info["sw_version"] = firmware
        self._attr_device_info = device_info
        self._host = entry.data[CONF_HOST]

    @property
    def available(self) -> bool:
        """Available while the last poll succeeded."""
        return super().available and self.coordinator.data is not None
