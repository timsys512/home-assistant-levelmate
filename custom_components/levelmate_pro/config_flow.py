"""Config flow for the LevelMate Pro integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_ADDRESS,
    CONF_DRIVING_SIDE,
    CONF_LENGTH_INCHES,
    CONF_ORIENTATION,
    CONF_WIDTH_INCHES,
    DEFAULT_DRIVING_SIDE,
    DEFAULT_LENGTH_INCHES,
    DEFAULT_ORIENTATION,
    DEFAULT_WIDTH_INCHES,
    DOMAIN,
    DRIVING_SIDE_CHOICES,
    ORIENTATION_CHOICES,
)

MANUAL_ENTRY_VALUE = "__manual__"


def _parameters_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_WIDTH_INCHES, default=defaults.get(CONF_WIDTH_INCHES, DEFAULT_WIDTH_INCHES)
            ): vol.Coerce(int),
            vol.Required(
                CONF_LENGTH_INCHES,
                default=defaults.get(CONF_LENGTH_INCHES, DEFAULT_LENGTH_INCHES),
            ): vol.Coerce(int),
            vol.Required(
                CONF_ORIENTATION,
                default=defaults.get(CONF_ORIENTATION, DEFAULT_ORIENTATION),
            ): vol.In(ORIENTATION_CHOICES),
            vol.Required(
                CONF_DRIVING_SIDE,
                default=defaults.get(CONF_DRIVING_SIDE, DEFAULT_DRIVING_SIDE),
            ): vol.In(DRIVING_SIDE_CHOICES),
        }
    )


class LevelMateProConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LevelMate Pro."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_address: str | None = None
        self._discovered_name: str | None = None
        self._discovered_devices: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle a discovered LevelMate Pro advertising the AA10 service."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovered_address = discovery_info.address
        self._discovered_name = discovery_info.name or discovery_info.address
        self.context["title_placeholders"] = {"name": self._discovered_name}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm a Bluetooth-discovered device, then ask for parameters."""
        if user_input is not None:
            return await self.async_step_parameters()
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"name": self._discovered_name or ""},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Handle a manually-started flow.

        The LevelMate Pro does not appear to advertise its custom AA10
        service UUID in the BLE advertisement packet itself (that's only
        visible after connecting and discovering GATT services), so we
        cannot filter nearby devices by service UUID here the way most
        Bluetooth integrations do. Instead: list every nearby connectable
        device (so you can pick yours by address/name), AND offer a manual
        "enter the address yourself" option, since you likely already know
        it from earlier BLE captures.
        """
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            if address == MANUAL_ENTRY_VALUE:
                return await self.async_step_manual_address()
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            self._discovered_address = address
            return await self.async_step_parameters()

        current_addresses = self._async_current_ids()
        for discovery_info in bluetooth.async_discovered_service_info(
            self.hass, connectable=True
        ):
            if discovery_info.address in current_addresses:
                continue
            self._discovered_devices[discovery_info.address] = (
                f"{discovery_info.name or 'Unknown'} ({discovery_info.address})"
            )

        choices = dict(self._discovered_devices)
        choices[MANUAL_ENTRY_VALUE] = "Enter address manually..."

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(choices)}),
        )

    async def async_step_manual_address(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Manual address entry fallback - for when the device isn't showing up
        in the list above (e.g. it's currently asleep; the LevelMate Pro
        powers down its radio after a period of no motion and only wakes on
        motion or a power-switch cycle - try moving the RV slightly or
        cycling its physical on/off switch, then retry setup).
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].upper()
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, address, connectable=True
            )
            if ble_device is None:
                errors["base"] = "device_not_found"
            else:
                self._discovered_address = address
                return await self.async_step_parameters()

        return self.async_show_form(
            step_id="manual_address",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
            errors=errors,
        )

    async def async_step_parameters(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask for width, length, mounting orientation, and driving side."""
        if user_input is not None:
            address = self._discovered_address
            assert address is not None
            name = self._discovered_devices.get(address, self._discovered_name or address)
            return self.async_create_entry(
                title=name,
                data={
                    CONF_ADDRESS: address,
                    CONF_WIDTH_INCHES: user_input[CONF_WIDTH_INCHES],
                    CONF_LENGTH_INCHES: user_input[CONF_LENGTH_INCHES],
                    CONF_ORIENTATION: user_input[CONF_ORIENTATION],
                    CONF_DRIVING_SIDE: user_input[CONF_DRIVING_SIDE],
                },
            )

        return self.async_show_form(
            step_id="parameters",
            data_schema=_parameters_schema({}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "LevelMateProOptionsFlow":
        return LevelMateProOptionsFlow()


class LevelMateProOptionsFlow(config_entries.OptionsFlow):
    """
    Lets the user change width/length/orientation/driving-side later.

    Deliberately has NO __init__ / self.config_entry assignment: recent Home
    Assistant versions inject `self.config_entry` automatically, and a
    custom __init__ that tries to set it manually raises an error (seen as
    "Config flow could not be loaded: 500 Internal Server Error") on those
    versions. Just use the inherited `self.config_entry` directly.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_parameters_schema(current),
        )
