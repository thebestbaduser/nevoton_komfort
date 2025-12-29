"""Sensor platform for Nevoton Komfort integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NevotonKomfortConfigEntry
from .const import (
    PARAM_HUMIDITY_REAL,
    PARAM_STATUS,
    PARAM_TEMPERATURE_REAL,
    PARAM_TIME_HEAT_REAL,
    PARAM_TIMER_OFFSET_REAL,
)
from .coordinator import NevotonKomfortCoordinator
from .entity import NevotonKomfortEntity

_LOGGER = logging.getLogger(__name__)


def _convert_minutes_to_time(value: int | None) -> str | None:
    """Convert minutes value to HH:MM format."""
    if value is None:
        return None
    hours = value // 60
    minutes = value % 60
    return f"{hours:02d}:{minutes:02d}"


@dataclass(frozen=True, kw_only=True)
class NevotonSensorEntityDescription(SensorEntityDescription):
    """Describes Nevoton Komfort sensor entity."""

    value_fn: Callable[[NevotonKomfortCoordinator], float | int | str | None]


SENSOR_DESCRIPTIONS: tuple[NevotonSensorEntityDescription, ...] = (
    NevotonSensorEntityDescription(
        key="temperature",
        translation_key="current_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda coord: coord.get_sensor_value(PARAM_TEMPERATURE_REAL),
    ),
    NevotonSensorEntityDescription(
        key="humidity",
        translation_key="current_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda coord: coord.get_sensor_value(PARAM_HUMIDITY_REAL),
    ),
    NevotonSensorEntityDescription(
        key="heat_time_remaining",
        translation_key="heat_time_remaining",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda coord: coord.get_timer_value(PARAM_TIME_HEAT_REAL),
    ),
    NevotonSensorEntityDescription(
        key="delayed_start_time",
        translation_key="delayed_start_time",
        icon="mdi:timer-outline",
        value_fn=lambda coord: _convert_minutes_to_time(
            coord.get_timer_value(PARAM_TIMER_OFFSET_REAL)
        ),
    ),
    NevotonSensorEntityDescription(
        key="status",
        translation_key="status",
        icon="mdi:information-outline",
        value_fn=lambda coord: coord.get_status(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NevotonKomfortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nevoton Komfort sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        NevotonKomfortSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class NevotonKomfortSensor(NevotonKomfortEntity, SensorEntity):
    """Sensor entity for Nevoton Komfort sauna controller."""

    entity_description: NevotonSensorEntityDescription

    def __init__(
        self,
        coordinator: NevotonKomfortCoordinator,
        description: NevotonSensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | str | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator)
