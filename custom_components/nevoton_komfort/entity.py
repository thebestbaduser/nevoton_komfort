"""Base entity for Nevoton Komfort integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NevotonKomfortCoordinator


class NevotonKomfortEntity(CoordinatorEntity[NevotonKomfortCoordinator]):
    """Base class for Nevoton Komfort entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NevotonKomfortCoordinator,
        entity_key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._entity_key = entity_key
        
        # Set unique_id using device ID and entity key
        device_id = coordinator.api.device_id or "unknown"
        self._attr_unique_id = f"{device_id}_{entity_key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        device_data = self.coordinator.device_info or {}
        device = device_data.get("device", {})
        
        return DeviceInfo(
            identifiers={(DOMAIN, device.get("id", "unknown"))},
            name="Nevoton Komfort",
            manufacturer="NEVOTON",
            model=device_data.get("moduleName", "KOMFORT-WF"),
            sw_version=device_data.get("firmwareVersion"),
            configuration_url=f"http://{device.get('ip', self.coordinator.api._host)}/human",
        )
