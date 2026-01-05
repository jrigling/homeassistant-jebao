"""Base entity for Jebao integration."""
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
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)

        self._device_id = device_id
        self._model = model
        self._host = host

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=f"Jebao {model}",
            manufacturer="Jebao",
            model=model,
            configuration_url=f"http://{host}:12416",
        )
