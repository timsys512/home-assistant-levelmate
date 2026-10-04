"""Switch entity for the LevelMate Pro integration."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LevelMateCoordinator, LevelMateData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: LevelMateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([LevelMateConnectionSwitch(coordinator, entry)])


class LevelMateConnectionSwitch(CoordinatorEntity[LevelMateCoordinator], SwitchEntity):
    """
    Turns Home Assistant's Bluetooth connection to the LevelMate Pro on/off.

    Most BLE peripherals, including the LevelMate Pro, only accept one
    connected "central" (phone/hub) at a time. While Home Assistant holds
    that connection, the official LevelMate app cannot connect to the
    device. Turn this switch OFF to have Home Assistant release the
    connection (so you can open the official app), then back ON when you're
    done to resume live sensor data here.
    """

    _attr_has_entity_name = True
    _attr_name = "Bluetooth Connection"
    _attr_icon = "mdi:bluetooth"
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator: LevelMateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.data['address']}_connection_switch"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data["address"])},
            name=entry.title,
            manufacturer="LogicBlue",
            model="LevelMate Pro",
        )

    @property
    def is_on(self) -> bool:
        """
        On = Home Assistant is (or is trying to stay) connected. Off = the
        user has intentionally paused the connection, e.g. to use the
        official app.
        """
        data: LevelMateData = self.coordinator.data
        return not (data and data.paused)

    @property
    def available(self) -> bool:
        # Always available/controllable, even if currently disconnected -
        # otherwise you couldn't turn it back on from the UI.
        return True

    async def async_turn_off(self, **kwargs) -> None:
        """Release the BLE connection so the official app can connect."""
        await self.coordinator.async_pause_connection()

    async def async_turn_on(self, **kwargs) -> None:
        """Resume the BLE connection to Home Assistant."""
        await self.coordinator.async_resume_connection()
