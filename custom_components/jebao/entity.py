"""Base entity for Jebao integration."""
from typing import Optional

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import JebaoDataUpdateCoordinator


class JebaoEntity(CoordinatorEntity[JebaoDataUpdateCoordinator]):
    """Base entity for Jebao devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: JebaoDataUpdateCoordinator,
        device_id: str,
        model: str,
        host: str,
        mac_address: Optional[str] = None,
        firmware_version: Optional[str] = None,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)

        self._device_id = device_id
        self._model = model
        self._host = host

        # Build device info
        device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=f"Jebao {model}",
            manufacturer="Jebao",
            model=model,
            serial_number=device_id,
            configuration_url=f"http://{host}:12416",
        )

        # Add MAC address as connection if available
        if mac_address:
            device_info["connections"] = {("mac", mac_address)}

        # Add firmware version if available
        if firmware_version:
            device_info["sw_version"] = firmware_version

        self._attr_device_info = device_info
