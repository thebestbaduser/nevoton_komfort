"""Switch platform for Nevoton Komfort integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NevotonKomfortConfigEntry
from .const import (
    PARAM_FAN,
    PARAM_HUMIDITY,
    PARAM_MAIN_POWER,
    PARAM_TIMER_OFFSET_CHECKBOX,
)
from .coordinator import NevotonKomfortCoordinator
from .entity import NevotonKomfortEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class NevotonSwitchEntityDescription(SwitchEntityDescription):
    """Describes Nevoton Komfort switch entity."""

    api_param: str


SWITCH_DESCRIPTIONS: tuple[NevotonSwitchEntityDescription, ...] = (
    NevotonSwitchEntityDescription(
        key="main_power",
        translation_key="main_power",
        api_param=PARAM_MAIN_POWER,
        device_class=SwitchDeviceClass.SWITCH,
    ),
    NevotonSwitchEntityDescription(
        key="fan",
        translation_key="fan",
        api_param=PARAM_FAN,
        device_class=SwitchDeviceClass.SWITCH,
    ),
    NevotonSwitchEntityDescription(
        key="humidity",
        translation_key="steam_generator",
        api_param=PARAM_HUMIDITY,
        device_class=SwitchDeviceClass.SWITCH,
    ),
    NevotonSwitchEntityDescription(
        key="timer_offset",
        translation_key="delayed_start",
        api_param=PARAM_TIMER_OFFSET_CHECKBOX,
        device_class=SwitchDeviceClass.SWITCH,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NevotonKomfortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nevoton Komfort switch entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        NevotonKomfortSwitch(coordinator, description)
        for description in SWITCH_DESCRIPTIONS
    )


class NevotonKomfortSwitch(NevotonKomfortEntity, SwitchEntity):
    """Switch entity for Nevoton Komfort sauna controller."""

    entity_description: NevotonSwitchEntityDescription

    def __init__(
        self,
        coordinator: NevotonKomfortCoordinator,
        description: NevotonSwitchEntityDescription,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.coordinator.get_switch_state(self.entity_description.api_param)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.coordinator.api.async_set_parameter(
            self.entity_description.api_param, 1
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.coordinator.api.async_set_parameter(
            self.entity_description.api_param, 0
        )
        await self.coordinator.async_request_refresh()
