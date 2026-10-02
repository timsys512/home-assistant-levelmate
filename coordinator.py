"""BLE connection + data coordinator for the LevelMate Pro integration."""
from __future__ import annotations

import logging
import struct
from dataclasses import dataclass, field

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CHAR_FRONT,
    CHAR_INSTALL_ORIENTATION,
    CHAR_PASSWORD,
    CHAR_RV_LENGTH,
    CHAR_RV_WIDTH,
    CHAR_SIDE,
    CHAR_TEMPERATURE,
    DOMAIN,
    install_orientation_to_device_byte,
)
from .levelmate_math import (
    CornerDeltas,
    celsius_to_fahrenheit,
    decode_float32_le,
    decode_int16_le,
    reconstruct_corners,
)
from .password import PasswordComputationError, compute_password

_LOGGER = logging.getLogger(__name__)

RECONNECT_DELAY_SECONDS = 15


@dataclass
class LevelMateData:
    """Latest known state, pushed to entities through the coordinator."""

    side_raw: int | None = None
    front_raw: int | None = None
    temperature_c: float | None = None
    temperature_f: float | None = None
    corners: CornerDeltas | None = None
    connected: bool = False


class LevelMateCoordinator(DataUpdateCoordinator[LevelMateData]):
    """
    Owns the BLE connection to one LevelMate Pro unit.

    Unlike a typical HA polling coordinator, this one is push-driven: BLE
    notifications call `_handle_notification`, which updates `self.data` and
    calls `async_set_updated_data` to notify entities immediately. There is
    no polling interval - `update_interval` is intentionally left as None.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        width_inches: int,
        length_inches: int,
        orientation: str,
        driving_side: str,
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.address = address
        self.width_inches = width_inches
        self.length_inches = length_inches
        self.orientation = orientation
        self.driving_side = driving_side

        self._client: BleakClient | None = None
        self.data = LevelMateData()

    async def async_connect(self) -> None:
        """Connects, writes the configured parameters, and subscribes to notifications."""
        ble_device: BLEDevice | None = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise ConnectionError(
                f"LevelMate Pro {self.address} not visible to Home Assistant's "
                "Bluetooth integration - is it powered on and in range of an "
                "active/local Bluetooth adapter or proxy?"
            )

        _LOGGER.debug("Connecting to LevelMate Pro %s", self.address)
        client = await establish_connection(
            BleakClientWithServiceCache, ble_device, self.address,
            disconnected_callback=self._handle_disconnected,
        )
        self._client = client

        try:
            await self._write_configured_parameters()
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning(
                "Could not write width/length/orientation to LevelMate Pro %s "
                "(%s). Live leveling data will still be read normally; only "
                "the on-device parameter write failed.",
                self.address, exc,
            )

        await client.start_notify(CHAR_SIDE, self._on_side)
        await client.start_notify(CHAR_FRONT, self._on_front)
        await client.start_notify(CHAR_TEMPERATURE, self._on_temperature)

        self.data.connected = True
        self.async_set_updated_data(self.data)
        _LOGGER.info("LevelMate Pro %s connected and subscribed", self.address)

    async def async_disconnect(self) -> None:
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self._client = None
        self.data.connected = False

    async def _authorize_next_write(self) -> bool:
        """
        Writes a fresh time-synced "password" to CHAR_PASSWORD, required
        immediately before each protected write (install orientation, RV
        width, RV length, etc.) or the device responds with
        BleakGATTProtocolErrorCode.INSUFFICIENT_AUTHORIZATION. See
        password.py for the full algorithm and its source in the app's
        bytecode. Returns False (and logs a clear warning) if the password
        can't be computed - e.g. the device's advertised name doesn't match
        the expected format - so callers can skip the protected write
        instead of crashing the whole integration.
        """
        client = self._client
        assert client is not None

        ble_device: BLEDevice | None = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        device_name = ble_device.name if ble_device else None
        try:
            password = compute_password(device_name)
        except PasswordComputationError as exc:
            _LOGGER.warning(
                "Could not compute the LevelMate Pro write-authorization "
                "password for %s (advertised name=%r): %s. Width/length/"
                "orientation will NOT be written to the device, but live "
                "leveling data should still work normally.",
                self.address, device_name, exc,
            )
            return False

        await client.write_gatt_char(CHAR_PASSWORD, password)
        return True

    async def _write_configured_parameters(self) -> None:
        """
        Writes width, length, and install orientation to the device - the
        same characteristics the official app writes during its setup
        wizard. See const.py for why width/length don't currently appear to
        affect the corner-delta numbers themselves, based on the app code we
        traced; they're written anyway for parity with the official setup.

        Each protected write needs its own freshly-authorized password
        immediately beforehand (the password is time-synced to the current
        minute/hour) - see _authorize_next_write().
        """
        client = self._client
        assert client is not None

        if not await self._authorize_next_write():
            return

        orientation_byte = install_orientation_to_device_byte(
            self.orientation, self.driving_side
        )
        await client.write_gatt_char(
            CHAR_INSTALL_ORIENTATION, bytes([orientation_byte & 0xFF])
        )

        if not await self._authorize_next_write():
            return
        await client.write_gatt_char(
            CHAR_RV_WIDTH, struct.pack("<h", int(self.width_inches))
        )

        if not await self._authorize_next_write():
            return
        await client.write_gatt_char(
            CHAR_RV_LENGTH, struct.pack("<h", int(self.length_inches))
        )

        _LOGGER.debug(
            "Wrote orientation=%s (byte=%d), width=%din, length=%din to %s",
            self.orientation, orientation_byte, self.width_inches,
            self.length_inches, self.address,
        )

    async def async_update_parameters(
        self, width_inches: int, length_inches: int, orientation: str, driving_side: str
    ) -> None:
        """Called when the user changes options; re-writes settings to the device."""
        self.width_inches = width_inches
        self.length_inches = length_inches
        self.orientation = orientation
        self.driving_side = driving_side
        if self._client is not None and self._client.is_connected:
            try:
                await self._write_configured_parameters()
            except Exception as exc:  # noqa: BLE001
                _LOGGER.warning(
                    "Could not write updated width/length/orientation to "
                    "LevelMate Pro %s (%s).", self.address, exc,
                )

    @callback
    def _handle_disconnected(self, client: BleakClient) -> None:
        _LOGGER.warning("LevelMate Pro %s disconnected", self.address)
        self.data.connected = False
        self.async_set_updated_data(self.data)

    def _recompute_corners_if_ready(self) -> None:
        if self.data.side_raw is not None and self.data.front_raw is not None:
            self.data.corners = reconstruct_corners(
                self.data.side_raw, self.data.front_raw
            )

    @callback
    def _on_side(self, _sender, raw: bytearray) -> None:
        value = decode_int16_le(bytes(raw))
        if value is None:
            return
        self.data.side_raw = value
        self._recompute_corners_if_ready()
        self.async_set_updated_data(self.data)

    @callback
    def _on_front(self, _sender, raw: bytearray) -> None:
        value = decode_int16_le(bytes(raw))
        if value is None:
            return
        self.data.front_raw = value
        self._recompute_corners_if_ready()
        self.async_set_updated_data(self.data)

    @callback
    def _on_temperature(self, _sender, raw: bytearray) -> None:
        value = decode_float32_le(bytes(raw))
        if value is None:
            return
        self.data.temperature_c = value
        self.data.temperature_f = celsius_to_fahrenheit(value)
        self.async_set_updated_data(self.data)
