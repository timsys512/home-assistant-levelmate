"""The LevelMate Pro integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ADDRESS,
    CONF_DRIVING_SIDE,
    CONF_LENGTH_INCHES,
    CONF_ORIENTATION,
    CONF_WIDTH_INCHES,
    DOMAIN,
)
from .coordinator import LevelMateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LevelMate Pro from a config entry."""
    data = {**entry.data, **entry.options}

    coordinator = LevelMateCoordinator(
        hass,
        address=data[CONF_ADDRESS],
        width_inches=data[CONF_WIDTH_INCHES],
        length_inches=data[CONF_LENGTH_INCHES],
        orientation=data[CONF_ORIENTATION],
        driving_side=data[CONF_DRIVING_SIDE],
    )

    await coordinator.async_connect()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: LevelMateCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_disconnect()
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update: re-write width/length/orientation to the device."""
    coordinator: LevelMateCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = {**entry.data, **entry.options}
    await coordinator.async_update_parameters(
        width_inches=data[CONF_WIDTH_INCHES],
        length_inches=data[CONF_LENGTH_INCHES],
        orientation=data[CONF_ORIENTATION],
        driving_side=data[CONF_DRIVING_SIDE],
    )
