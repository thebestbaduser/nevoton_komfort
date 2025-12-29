"""The Nevoton Komfort integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NevotonKomfortApi
from .const import DOMAIN
from .coordinator import NevotonKomfortCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.NUMBER,
]

type NevotonKomfortConfigEntry = ConfigEntry[NevotonKomfortCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NevotonKomfortConfigEntry,
) -> bool:
    """Set up Nevoton Komfort from a config entry."""
    session = async_get_clientsession(hass)
    
    api = NevotonKomfortApi(
        host=entry.data[CONF_HOST],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )

    coordinator = NevotonKomfortCoordinator(hass, entry, api)

    # Fetch device info first
    await coordinator._async_setup()

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in entry runtime data
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: NevotonKomfortConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
