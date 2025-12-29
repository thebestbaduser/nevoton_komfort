"""Climate platform for Nevoton Komfort integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NevotonKomfortConfigEntry
from .const import (
    PARAM_HEAT,
    PARAM_MAIN_POWER,
    PARAM_TEMPERATURE_REAL,
    PARAM_TEMPERATURE_SET,
    TEMP_MAX,
    TEMP_MIN,
)
from .coordinator import NevotonKomfortCoordinator
from .entity import NevotonKomfortEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NevotonKomfortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nevoton Komfort climate entity."""
    coordinator = entry.runtime_data
    async_add_entities([NevotonKomfortClimate(coordinator)])


class NevotonKomfortClimate(NevotonKomfortEntity, ClimateEntity):
    """Climate entity for Nevoton Komfort sauna controller."""

    _attr_translation_key = "sauna"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_min_temp = TEMP_MIN
    _attr_max_temp = TEMP_MAX
    _attr_target_temperature_step = 1
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator: NevotonKomfortCoordinator) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, "climate")
        self._attr_name = None  # Use device name

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.coordinator.get_sensor_value(PARAM_TEMPERATURE_REAL)

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self.coordinator.get_sensor_value(PARAM_TEMPERATURE_SET)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        main_power = self.coordinator.get_switch_state(PARAM_MAIN_POWER)
        heat_on = self.coordinator.get_switch_state(PARAM_HEAT)
        
        if main_power and heat_on:
            return HVACMode.HEAT
        return HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.HEAT:
            # Turn on main power and heater
            await self.coordinator.api.async_set_parameter(PARAM_MAIN_POWER, 1)
            await self.coordinator.api.async_set_parameter(PARAM_HEAT, 1)
        else:
            # Turn off heater (keep main power for other functions)
            await self.coordinator.api.async_set_parameter(PARAM_HEAT, 0)
        
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.api.async_set_parameter(
                PARAM_TEMPERATURE_SET,
                int(temperature),
            )
            await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Turn on the sauna."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn off the sauna."""
        await self.async_set_hvac_mode(HVACMode.OFF)
