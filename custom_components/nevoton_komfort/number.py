"""Number platform for Nevoton Komfort integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NevotonKomfortConfigEntry
from .const import (
    HUMIDITY_MAX,
    HUMIDITY_MIN,
    PARAM_HUMIDITY_SET,
    PARAM_TIME_HEAT_SET,
    PARAM_TIMER_OFFSET_SET,
)
from .coordinator import NevotonKomfortCoordinator
from .entity import NevotonKomfortEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class NevotonNumberEntityDescription(NumberEntityDescription):
    """Describes Nevoton Komfort number entity."""

    api_param: str
    value_fn: Callable[[NevotonKomfortCoordinator], float | None]


NUMBER_DESCRIPTIONS: tuple[NevotonNumberEntityDescription, ...] = (
    NevotonNumberEntityDescription(
        key="target_humidity",
        translation_key="target_humidity",
        device_class=NumberDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=HUMIDITY_MIN,
        native_max_value=HUMIDITY_MAX,
        native_step=1,
        mode=NumberMode.SLIDER,
        api_param=PARAM_HUMIDITY_SET,
        value_fn=lambda coord: coord.get_sensor_value(PARAM_HUMIDITY_SET),
    ),
    NevotonNumberEntityDescription(
        key="heat_timer",
        translation_key="heat_timer",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=0,
        native_max_value=360,  # 6 hours max
        native_step=5,
        mode=NumberMode.BOX,
        api_param=PARAM_TIME_HEAT_SET,
        value_fn=lambda coord: coord.get_timer_value(PARAM_TIME_HEAT_SET),
    ),
    NevotonNumberEntityDescription(
        key="delayed_start_timer",
        translation_key="delayed_start_timer",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=0,
        native_max_value=1440,  # 24 hours max
        native_step=5,
        mode=NumberMode.BOX,
        icon="mdi:timer-sand",
        api_param=PARAM_TIMER_OFFSET_SET,
        value_fn=lambda coord: coord.get_timer_value(PARAM_TIMER_OFFSET_SET),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NevotonKomfortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nevoton Komfort number entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        NevotonKomfortNumber(coordinator, description)
        for description in NUMBER_DESCRIPTIONS
    )


class NevotonKomfortNumber(NevotonKomfortEntity, NumberEntity):
    """Number entity for Nevoton Komfort sauna controller."""

    entity_description: NevotonNumberEntityDescription

    def __init__(
        self,
        coordinator: NevotonKomfortCoordinator,
        description: NevotonNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self.coordinator.api.async_set_parameter(
            self.entity_description.api_param,
            int(value),
        )
        await self.coordinator.async_request_refresh()
