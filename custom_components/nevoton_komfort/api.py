"""API client for Nevoton Komfort sauna controller."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import socket
import time
from typing import Any
from urllib.parse import urlencode

from .const import (
    API_DEVICE_DESCRIPTION,
    API_GET_INPUTS,
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
        self._host = host
        self._password_hash = self._hash_password(password)
        self._device_info: dict[str, Any] | None = None

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
        is_write: bool = False
    ) -> dict[str, Any]:
        """Make raw HTTP request using sockets to handle buggy headers."""
        url_path = self._build_url(endpoint, params)
        
        request = (
            f"GET {url_path} HTTP/1.0\r\n"
            f"Host: {self._host}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )
        
        def sync_request() -> str:
            """Synchronous socket request with fresh connection each time."""
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)  # Reduced timeout to fail faster
                sock.connect((self._host, 80))
                
                sock.sendall(request.encode())
                
                # For write operations, controller may not send response body
                # Just wait a bit for command to be processed and return empty
                if is_write:
                    time.sleep(0.2)
                    return ""
                
                response = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response += chunk
                    # Early exit if we have complete JSON response
                    if b'}' in response and response.strip().endswith(b'}'):
                        break
                
                return response.decode('utf-8', errors='ignore')
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
        
        # For write operations, empty response is OK
        if not response_text:
            return {}
        
        # Extract JSON from response (find the JSON part after headers)
        json_start = response_text.find('{')
        if json_start == -1:
            raise NevotonApiError(f"No JSON in response: {response_text[:200]}")
        
        json_text = response_text[json_start:]
        # Find the end of JSON (last closing brace)
        json_end = json_text.rfind('}')
        if json_end != -1:
            json_text = json_text[:json_end + 1]
        
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as err:
            raise NevotonApiError(f"Invalid JSON: {err}") from err
        
        # Check for API errors
        if "error_api" in data:
            error_code = data["error_api"]
            if error_code == 6:
                raise NevotonAuthError("Invalid password")
            raise NevotonApiError(f"API error: {error_code}")
        
        if "error_device" in data and data["error_device"] != 0:
            raise NevotonApiError(f"Device error: {data['error_device']}")
        
        return data

    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        is_write: bool = False,
    ) -> dict[str, Any]:
        """Make API request."""
        return await self._raw_request(endpoint, params, is_write)

    async def async_get_device_info(self) -> dict[str, Any]:
        """Get device information."""
        data = await self._request(API_DEVICE_DESCRIPTION)
        self._device_info = data
        return data

    async def async_get_state(self) -> dict[str, Any]:
        """Get current state of all specific inputs."""
        data = await self._request(
            API_GET_INPUTS,
            {
                PARAM_TYPE: TYPE_SPECIFIC,
                PARAM_NUMBER: "All",
            },
        )
        
        # Extract the value from the response structure
        if "inputs" in data and "data" in data["inputs"]:
            inputs_data = data["inputs"]["data"]
            if inputs_data and len(inputs_data) > 0:
                return inputs_data[0].get("value", {})
        
        return {}

    async def async_set_parameter(
        self,
        parameter: str,
        value: int | float,
    ) -> bool:
        """Set a specific parameter."""
        data = await self._request(
            API_SET_OUTPUTS,
            {
                PARAM_TYPE: TYPE_SPECIFIC,
                PARAM_NUMBER: 0,
                PARAM_SP_NAME: parameter,
                PARAM_VALUE: int(value),
            },
            is_write=True,
        )
        
        # Device may return transport-level success but channel-level failure.
        if "outputs" not in data:
            raise NevotonApiError("Invalid set response: missing 'outputs'")

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
