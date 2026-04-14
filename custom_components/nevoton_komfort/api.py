"""API client for Nevoton Komfort sauna controller."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import socket
from typing import Any
from urllib.parse import urlencode, urlsplit

from .const import (
    API_DEVICE_DESCRIPTION,
    API_GET_INPUTS,
    API_GET_OUTPUTS,
    API_SET_OUTPUTS,
    PARAM_HASH,
    PARAM_NUMBER,
    PARAM_SP_NAME,
    PARAM_TYPE,
    PARAM_VALUE,
    TYPE_SPECIFIC,
)

_LOGGER = logging.getLogger(__name__)


class NevotonApiError(Exception):
    """Base exception for Nevoton API errors."""

    def __init__(
        self,
        message: str,
        *,
        error_api: int | None = None,
        error_device: int | None = None,
    ) -> None:
        """Initialize the API error."""
        super().__init__(message)
        self.error_api = error_api
        self.error_device = error_device


class NevotonAuthError(NevotonApiError):
    """Authentication error."""


class NevotonConnectionError(NevotonApiError):
    """Connection error."""


class NevotonKomfortApi:
    """API client for Nevoton Komfort sauna controller.

    Note: The Nevoton device has buggy HTTP headers (sends HTTP/1.1 200 OK twice),
    which breaks standard HTTP clients. We use raw socket communication instead.
    """

    def __init__(
        self,
        host: str,
        password: str,
    ) -> None:
        """Initialize API client."""
        parsed = self._parse_host(host)
        self._host = parsed["host"]
        self._port = parsed["port"]
        self._host_header = parsed["host_header"]
        self._base_url = parsed["base_url"]
        self._password_hash = self._hash_password(password)
        self._device_info: dict[str, Any] | None = None

    @staticmethod
    def _parse_host(host: str) -> dict[str, Any]:
        """Parse a configured host value into socket connection parts."""
        normalized_host = host.strip().rstrip("/")
        split = urlsplit(
            normalized_host if "://" in normalized_host else f"http://{normalized_host}"
        )
        hostname = split.hostname or normalized_host
        port = split.port or 80
        host_header = hostname if port == 80 else f"{hostname}:{port}"
        base_url = f"http://{host_header}"
        return {
            "host": hostname,
            "port": port,
            "host_header": host_header,
            "base_url": base_url,
        }

    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash password using SHA-1.

        Note: SHA-1 is used because it's what the device firmware expects.
        While SHA-1 is cryptographically weak, it's acceptable here since:
        1. The hash is only used for device authentication, not data protection
        2. The device firmware requires this specific algorithm
        3. Communication is typically on a local network
        """
        return hashlib.sha1(password.encode()).hexdigest()

    def _build_url(self, endpoint: str, params: dict[str, Any] | None = None) -> str:
        """Build URL path with query parameters."""
        query_params: dict[str, Any] = dict(params or {})
        query_params[PARAM_HASH] = self._password_hash
        query = urlencode(query_params)
        return f"{endpoint}?{query}"

    async def _raw_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        is_write: bool = False,
    ) -> dict[str, Any]:
        """Make raw HTTP request using sockets to handle buggy headers."""
        url_path = self._build_url(endpoint, params)

        request = (
            f"GET {url_path} HTTP/1.0\r\n"
            f"Host: {self._host_header}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )

        def sync_request() -> str:
            """Synchronous socket request with fresh connection each time."""
            sock = None
            response = b""
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((self._host, self._port))

                sock.sendall(request.encode())

                # Documented API returns JSON for writes, but some firmware builds
                # complete the command without sending a response body.
                if is_write:
                    sock.settimeout(1)

                while True:
                    try:
                        chunk = sock.recv(4096)
                    except socket.timeout:
                        if is_write:
                            break
                        raise

                    if not chunk:
                        break

                    response += chunk
                    if b"}" in response and response.strip().endswith(b"}"):
                        break

                return response.decode("utf-8", errors="ignore")
            except socket.timeout:
                raise
            except Exception:
                raise
            finally:
                if sock is not None:
                    try:
                        sock.close()
                    except Exception:
                        pass

        try:
            loop = asyncio.get_running_loop()
            response_text = await loop.run_in_executor(None, sync_request)
        except socket.timeout as err:
            raise NevotonConnectionError("Connection timeout") from err
        except socket.error as err:
            raise NevotonConnectionError(f"Connection error: {err}") from err

        if not response_text:
            return {}

        json_start = response_text.find("{")
        if json_start == -1:
            if is_write:
                _LOGGER.debug(
                    "No JSON body returned for write request to %s; assuming success",
                    endpoint,
                )
                return {}
            raise NevotonApiError(f"No JSON in response: {response_text[:200]}")

        json_text = response_text[json_start:]
        json_end = json_text.rfind("}")
        if json_end != -1:
            json_text = json_text[: json_end + 1]

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as err:
            raise NevotonApiError(f"Invalid JSON: {err}") from err

        if "error_api" in data:
            error_code = data["error_api"]
            if error_code == 6:
                raise NevotonAuthError("Invalid password", error_api=error_code)
            raise NevotonApiError(
                f"API error: {error_code}",
                error_api=error_code,
            )

        if "error_device" in data and data["error_device"] != 0:
            raise NevotonApiError(
                f"Device error: {data['error_device']}",
                error_device=data["error_device"],
            )

        return data

    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        is_write: bool = False,
    ) -> dict[str, Any]:
        """Make API request."""
        result = await self._raw_request(endpoint, params, is_write=is_write)

        if is_write:
            if not result:
                _LOGGER.debug("Empty response for write operation (considered success)")
                return {"success": True}

            if "error_api" in result:
                raise NevotonApiError(f"API Error code: {result['error_api']}")
            if "error_device" in result and result["error_device"] != 0:
                raise NevotonApiError(f"Device Error code: {result['error_device']}")

            return result

        if not result:
            raise NevotonConnectionError("Empty response from device")

        return result

    async def _async_get_specific_values(
        self,
        endpoint: str,
        response_key: str,
    ) -> dict[str, Any]:
        """Read and flatten all values from a specific channel type."""
        for number in ("All", 0):
            try:
                data = await self._request(
                    endpoint,
                    {
                        PARAM_TYPE: TYPE_SPECIFIC,
                        PARAM_NUMBER: number,
                    },
                )
            except NevotonApiError as err:
                if number == "All" and err.error_api in {2, 3}:
                    _LOGGER.debug(
                        "Specific request %s with number=All failed for %s, retrying number=0",
                        response_key,
                        endpoint,
                    )
                    continue
                if err.error_api == 2:
                    _LOGGER.debug(
                        "Device does not expose %s for %s specific channels",
                        response_key,
                        endpoint,
                    )
                    return {}
                raise

            state: dict[str, Any] = {}
            channel_data = data.get(response_key, {}).get("data", [])
            for channel in channel_data:
                value = channel.get("value")
                if isinstance(value, dict):
                    state.update(self._flatten_specific_value(value))

            if state or number == 0:
                return state

            _LOGGER.debug(
                "Specific request %s with number=All returned no values for %s, retrying number=0",
                response_key,
                endpoint,
            )

        return {}

    def _flatten_specific_value(self, value: dict[str, Any]) -> dict[str, Any]:
        """Flatten nested specific-channel payloads into a single key/value map."""
        flattened: dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(item, dict):
                flattened.update(self._flatten_specific_value(item))
            else:
                flattened[key] = item
        return flattened

    async def async_get_device_info(self) -> dict[str, Any]:
        """Get device information."""
        data = await self._request(API_DEVICE_DESCRIPTION)
        self._device_info = data
        return data

    async def async_get_state(self) -> dict[str, Any]:
        """Get current state from the controller specific channel."""
        state = await self._async_get_specific_values(API_GET_INPUTS, "inputs")
        if state:
            return state

        _LOGGER.debug(
            "Specific inputs returned no values, falling back to specific outputs"
        )
        return await self._async_get_specific_values(API_GET_OUTPUTS, "outputs")

    async def async_set_parameter(
        self,
        parameter: str,
        value: int | float,
    ) -> bool:
        """Set a specific parameter."""
        request_params = {
            PARAM_TYPE: TYPE_SPECIFIC,
            PARAM_NUMBER: 0,
            PARAM_SP_NAME: parameter,
            PARAM_VALUE: int(value),
        }
        for attempt in range(2):
            try:
                data = await self._request(
                    API_SET_OUTPUTS,
                    request_params,
                    is_write=True,
                )
                break
            except NevotonConnectionError:
                if attempt == 1:
                    raise
                _LOGGER.warning(
                    "Timed out while writing %s, retrying once",
                    parameter,
                )
                await asyncio.sleep(0.5)

        # Device may return transport-level success but channel-level failure.
        # Some firmware versions return empty or minimal response on success.
        if "outputs" not in data:
            _LOGGER.debug(
                "Set response missing 'outputs' key, assuming success if no errors"
            )
            return True

        error_ch = data["outputs"].get("error_ch", 1)
        if error_ch != 0:
            raise NevotonApiError(
                f"Failed to set parameter '{parameter}', error_ch={error_ch}"
            )
        return True

    async def async_close(self) -> None:
        """Close the client and release resources."""
        pass  # No persistent connections to close anymore

    @property
    def host(self) -> str:
        """Return the host address."""
        return self._host

    @property
    def base_url(self) -> str:
        """Return the configured device base URL."""
        return self._base_url

    @property
    def device_id(self) -> str | None:
        """Return device ID."""
        if self._device_info:
            return self._device_info.get("device", {}).get("id")
        return None

    @property
    def device_mac(self) -> str | None:
        """Return device MAC address."""
        if self._device_info:
            return self._device_info.get("device", {}).get("macSTA")
        return None

    @property
    def firmware_version(self) -> str | None:
        """Return firmware version."""
        if self._device_info:
            return self._device_info.get("firmwareVersion")
        return None

    @property
    def model_name(self) -> str | None:
        """Return model name."""
        if self._device_info:
            return self._device_info.get("moduleName")
        return None
