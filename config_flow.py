"""Config flow for Nevoton Komfort integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NevotonKomfortApi, NevotonApiError, NevotonAuthError, NevotonConnectionError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PASSWORD, default="admin"): str,
    }
)


class NevotonKomfortConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nevoton Komfort."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = NevotonKomfortApi(
                host=user_input[CONF_HOST],
                password=user_input[CONF_PASSWORD],
                session=session,
            )

            try:
                device_info = await api.async_get_device_info()
            except NevotonAuthError:
                errors["base"] = "invalid_auth"
            except NevotonConnectionError:
                errors["base"] = "cannot_connect"
            except NevotonApiError:
                errors["base"] = "unknown"
            else:
                # Use device ID as unique identifier
                device_id = device_info.get("device", {}).get("id")
                if device_id:
                    await self.async_set_unique_id(device_id)
                    self._abort_if_unique_id_configured()

                # Get model name for title
                model_name = device_info.get("moduleName", "Nevoton Komfort")

                return self.async_create_entry(
                    title=model_name,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = NevotonKomfortApi(
                host=user_input[CONF_HOST],
                password=user_input[CONF_PASSWORD],
                session=session,
            )

            try:
                device_info = await api.async_get_device_info()
            except NevotonAuthError:
                errors["base"] = "invalid_auth"
            except NevotonConnectionError:
                errors["base"] = "cannot_connect"
            except NevotonApiError:
                errors["base"] = "unknown"
            else:
                # Verify we're reconfiguring the same device
                device_id = device_info.get("device", {}).get("id")
                if device_id:
                    await self.async_set_unique_id(device_id)
                    self._abort_if_unique_id_mismatch(reason="wrong_device")

                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )

        reconfigure_entry = self._get_reconfigure_entry()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=reconfigure_entry.data.get(CONF_HOST),
                    ): str,
                    vol.Required(
                        CONF_PASSWORD,
                        default=reconfigure_entry.data.get(CONF_PASSWORD),
                    ): str,
                }
            ),
            errors=errors,
        )
