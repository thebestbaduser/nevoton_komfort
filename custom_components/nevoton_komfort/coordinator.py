"""DataUpdateCoordinator for Nevoton Komfort integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import NevotonKomfortApi, NevotonApiError, NevotonAuthError, NevotonConnectionError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class NevotonKomfortCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage data updates from Nevoton Komfort device."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: NevotonKomfortApi,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self._device_info: dict[str, Any] | None = None

    async def _async_setup(self) -> None:
        """Set up the coordinator - fetch device info."""
        try:
            self._device_info = await self.api.async_get_device_info()
        except NevotonAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except NevotonApiError as err:
            raise UpdateFailed(f"Error fetching device info: {err}") from err

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            return await self.api.async_get_state()
        except NevotonAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except NevotonConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err
        except NevotonApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    @property
    def device_info(self) -> dict[str, Any] | None:
        """Return device info."""
        return self._device_info

    def get_switch_state(self, key: str) -> bool:
        """Get switch state from data."""
        if self.data:
            return self.data.get(key, 0) == 1
        return False

    def get_sensor_value(self, key: str) -> float | int | None:
        """Get sensor value from data."""
        if self.data:
            return self.data.get(key)
        return None

    def get_timer_value(self, key: str) -> int | None:
        """Get timer value from data."""
        if self.data:
            return self.data.get(key)
        return None

    def get_dimmer_value(self, key: str) -> int | None:
        """Get dimmer value from data."""
        if self.data:
            return self.data.get(key)
        return None

    def get_status(self) -> int:
        """Get device status."""
        if self.data:
            return self.data.get("Status", 0)
        return 0
