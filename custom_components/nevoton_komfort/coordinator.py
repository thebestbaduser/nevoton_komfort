"""DataUpdateCoordinator for Nevoton Komfort integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import NevotonKomfortApi, NevotonApiError, NevotonAuthError, NevotonConnectionError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)
_PARAMETER_SPLIT_RE = re.compile(r"(?<!^)(?=[A-Z])|[^0-9A-Za-z]+")


def _normalize_parameter_name(name: str) -> str:
    """Normalize a controller parameter name for fuzzy matching."""
    return "".join(ch.lower() for ch in name if ch.isalnum())


def _parameter_tokens(name: str) -> set[str]:
    """Split a parameter name into fuzzy-match tokens."""
    return {
        token.lower()
        for token in _PARAMETER_SPLIT_RE.split(name)
        if token
    }


def _match_score(expected: str, candidate: str) -> int:
    """Score how likely two parameter names refer to the same controller field."""
    if expected == candidate:
        return 100

    expected_normalized = _normalize_parameter_name(expected)
    candidate_normalized = _normalize_parameter_name(candidate)
    if expected_normalized == candidate_normalized:
        return 90

    expected_tokens = _parameter_tokens(expected)
    candidate_tokens = _parameter_tokens(candidate)
    common_tokens = expected_tokens & candidate_tokens
    if not common_tokens:
        return 0

    if expected_tokens == candidate_tokens:
        return 80
    if expected_tokens <= candidate_tokens or candidate_tokens <= expected_tokens:
        return 60 + len(common_tokens)
    return 20 + len(common_tokens)


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
        self._parameter_aliases: dict[str, str] = {}
        self._logged_resolutions: set[tuple[str, str]] = set()
        self._logged_missing_parameters: set[str] = set()
        self._consecutive_update_failures = 0
        self._post_write_refresh_task: asyncio.Task[None] | None = None

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
            state = await self.api.async_get_state()
            if not state:
                self._consecutive_update_failures += 1
                _LOGGER.warning(
                    "Device returned no specific parameters. "
                    "Check /help/specific on the controller to confirm the parameter names."
                )
                if self.data and self._consecutive_update_failures <= 2:
                    _LOGGER.warning(
                        "Keeping the last known device state after an empty response "
                        "(transient failure %s/2).",
                        self._consecutive_update_failures,
                    )
                    return self.data
                return state

            self._consecutive_update_failures = 0
            return state
        except NevotonAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except NevotonConnectionError as err:
            self._consecutive_update_failures += 1
            if self.data and self._consecutive_update_failures <= 2:
                _LOGGER.warning(
                    "Temporary connection error while refreshing state, keeping the "
                    "last known values (%s/2): %s",
                    self._consecutive_update_failures,
                    err,
                )
                return self.data
            raise UpdateFailed(f"Connection error: {err}") from err
        except NevotonApiError as err:
            self._consecutive_update_failures += 1
            if self.data and self._consecutive_update_failures <= 2:
                _LOGGER.warning(
                    "Temporary API error while refreshing state, keeping the last "
                    "known values (%s/2): %s",
                    self._consecutive_update_failures,
                    err,
                )
                return self.data
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def _resolve_parameter_name(self, key: str) -> str:
        """Resolve an expected parameter name to the closest live controller field."""
        if not self.data:
            return self._parameter_aliases.get(key, key)

        if key in self.data:
            self._parameter_aliases[key] = key
            return key

        if alias := self._parameter_aliases.get(key):
            return alias

        best_candidate: str | None = None
        best_score = 0
        ambiguous = False

        for candidate in self.data:
            score = _match_score(key, candidate)
            if score > best_score:
                best_candidate = candidate
                best_score = score
                ambiguous = False
            elif score and score == best_score:
                ambiguous = True

        if best_candidate and best_score >= 60 and not ambiguous:
            self._parameter_aliases[key] = best_candidate
            resolution = (key, best_candidate)
            if resolution not in self._logged_resolutions:
                _LOGGER.info(
                    "Resolved controller parameter %s -> %s",
                    key,
                    best_candidate,
                )
                self._logged_resolutions.add(resolution)
            return best_candidate

        if key not in self._logged_missing_parameters:
            _LOGGER.warning(
                "Controller parameter %s was not found in live data. Available keys: %s",
                key,
                ", ".join(sorted(self.data.keys())) or "<none>",
            )
            self._logged_missing_parameters.add(key)

        return key

    async def async_set_parameter(self, key: str, value: int | float) -> bool:
        """Resolve and write a controller parameter."""
        return await self.api.async_set_parameter(
            self._resolve_parameter_name(key),
            value,
        )

    def apply_local_update(self, key: str, value: int | float) -> None:
        """Apply a successful write to the local coordinator cache."""
        resolved_key = self._resolve_parameter_name(key)
        new_data = dict(self.data or {})
        new_data[resolved_key] = int(value)
        self._consecutive_update_failures = 0
        self.async_set_updated_data(new_data)

    async def async_refresh_after_write(self) -> None:
        """Schedule a refresh after a write without blocking the service call."""
        if self._post_write_refresh_task and not self._post_write_refresh_task.done():
            self._post_write_refresh_task.cancel()

        self._post_write_refresh_task = self.hass.async_create_task(
            self._async_delayed_refresh_after_write()
        )

    async def _async_delayed_refresh_after_write(self) -> None:
        """Run a delayed refresh after a write command."""
        try:
            await asyncio.sleep(1)
            await self.async_request_refresh()
        except asyncio.CancelledError:
            raise
        except Exception as err:
            _LOGGER.warning("Post-write refresh failed: %s", err)

    @property
    def device_info(self) -> dict[str, Any] | None:
        """Return device info."""
        return self._device_info

    def get_switch_state(self, key: str) -> bool:
        """Get switch state from data."""
        if self.data:
            value = self.data.get(self._resolve_parameter_name(key), 0)
            return value == 1
        return False

    def get_sensor_value(self, key: str) -> float | int | None:
        """Get sensor value from data."""
        if self.data:
            return self.data.get(self._resolve_parameter_name(key))
        return None

    def get_timer_value(self, key: str) -> int | None:
        """Get timer value from data."""
        if self.data:
            return self.data.get(self._resolve_parameter_name(key))
        return None

    def get_dimmer_value(self, key: str) -> int | None:
        """Get dimmer value from data."""
        if self.data:
            return self.data.get(self._resolve_parameter_name(key))
        return None

    def get_status(self) -> int | None:
        """Get device status."""
        if self.data:
            return self.data.get(self._resolve_parameter_name("Status"))
        return None
