"""Light platform for Nevoton Komfort integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NevotonKomfortConfigEntry
from .const import (
    LIGHT_DIMMER_MAX,
    PARAM_LIGHT,
    PARAM_LIGHT_DIMMER,
)
from .coordinator import NevotonKomfortCoordinator
from .entity import NevotonKomfortEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NevotonKomfortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nevoton Komfort light entity."""
    coordinator = entry.runtime_data
    async_add_entities([NevotonKomfortLight(coordinator)])


class NevotonKomfortLight(NevotonKomfortEntity, LightEntity):
    """Light entity for Nevoton Komfort sauna controller."""

    _attr_translation_key = "light"
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, coordinator: NevotonKomfortCoordinator) -> None:
        """Initialize the light entity."""
        super().__init__(coordinator, "light")

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.coordinator.get_switch_state(PARAM_LIGHT)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light (0-255)."""
        dimmer = self.coordinator.get_dimmer_value(PARAM_LIGHT_DIMMER)
        if dimmer is not None:
            # Convert 0-6 scale to 0-255
            # When dimmer is 0, light might still be on via Light_switch
            # Dimmer 1-6 maps to brightness levels
            if dimmer == 0:
                return 42  # Minimum visible brightness when on
            return int((dimmer / LIGHT_DIMMER_MAX) * 255)
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        # First, turn on the light switch
        await self.coordinator.api.async_set_parameter(PARAM_LIGHT, 1)
        
        # Then set brightness if provided
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            # Convert 0-255 to 1-6 (0 means off on the device)
            dimmer_value = max(1, min(LIGHT_DIMMER_MAX, round(brightness / 255 * LIGHT_DIMMER_MAX)))
            await self.coordinator.api.async_set_parameter(PARAM_LIGHT_DIMMER, dimmer_value)
        
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self.coordinator.api.async_set_parameter(PARAM_LIGHT, 0)
        await self.coordinator.async_request_refresh()
