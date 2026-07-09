"""Light platform for Nevoton Komfort integration."""

from __future__ import annotations

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
        if dimmer is None:
            return None

        # Convert 0-6 scale to 0-255.
        # Dimmer 0 still maps to a minimum visible level when the light switch is on.
        if dimmer <= 0:
            return int(255 / LIGHT_DIMMER_MAX)
        return int((min(dimmer, LIGHT_DIMMER_MAX) / LIGHT_DIMMER_MAX) * 255)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        # First, turn on the light switch
        await self.coordinator.async_set_parameter(PARAM_LIGHT, 1)
        self.coordinator.apply_local_update(PARAM_LIGHT, 1)

        # Then set brightness if provided
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            # Convert 0-255 to 1-6 (0 means off on the device)
            dimmer_value = max(
                1,
                min(LIGHT_DIMMER_MAX, round(brightness / 255 * LIGHT_DIMMER_MAX)),
            )
            await self.coordinator.async_set_parameter(PARAM_LIGHT_DIMMER, dimmer_value)
            self.coordinator.apply_local_update(PARAM_LIGHT_DIMMER, dimmer_value)

        await self.coordinator.async_refresh_after_write()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self.coordinator.async_set_parameter(PARAM_LIGHT, 0)
        self.coordinator.apply_local_update(PARAM_LIGHT, 0)
        await self.coordinator.async_refresh_after_write()
