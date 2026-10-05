"""Sensor entities for the LevelMate Pro integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LevelMateCoordinator, LevelMateData

CORNER_SENSORS = [
    ("driver_front_in", "Driver Front Corner"),
    ("passenger_front_in", "Passenger Front Corner"),
    ("driver_back_in", "Driver Back Corner"),
    ("passenger_back_in", "Passenger Back Corner"),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: LevelMateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        LevelMateCornerSensor(coordinator, entry, attr, label)
        for attr, label in CORNER_SENSORS
    ]
    entities.append(LevelMateTemperatureSensor(coordinator, entry))
    entities.append(LevelMateReferenceCornerSensor(coordinator, entry))
    entities.append(LevelMateRawSideSensor(coordinator, entry))
    entities.append(LevelMateRawFrontSensor(coordinator, entry))

    async_add_entities(entities)


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.data["address"])},
        name=entry.title,
        manufacturer="LogicBlue",
        model="LevelMate Pro",
    )


class _LevelMateBaseSensor(CoordinatorEntity[LevelMateCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: LevelMateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = _device_info(entry)

    @property
    def available(self) -> bool:
        data: LevelMateData = self.coordinator.data
        return bool(data and data.connected)


class LevelMateCornerSensor(_LevelMateBaseSensor):
    """One of the four corner height-delta readings, in inches."""

    _attr_native_unit_of_measurement = "in"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:angle-acute"

    def __init__(
        self, coordinator: LevelMateCoordinator, entry: ConfigEntry, attr: str, label: str
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr = attr
        self._attr_name = label
        self._attr_unique_id = f"{entry.data['address']}_{attr}"

    @property
    def native_value(self) -> float | None:
        data: LevelMateData = self.coordinator.data
        if not data or data.corners is None:
            return None
        return getattr(data.corners, self._attr)

    @property
    def available(self) -> bool:
        data: LevelMateData = self.coordinator.data
        return bool(data and data.connected and data.corners is not None)


class LevelMateReferenceCornerSensor(_LevelMateBaseSensor):
    """Which corner is currently the reference (already-highest, delta=0)."""

    _attr_name = "Reference Corner"
    _attr_icon = "mdi:axis-arrow"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: LevelMateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data['address']}_reference_corner"

    @property
    def native_value(self) -> str | None:
        data: LevelMateData = self.coordinator.data
        if not data or data.corners is None:
            return None
        return data.corners.reference_corner

    @property
    def available(self) -> bool:
        data: LevelMateData = self.coordinator.data
        return bool(data and data.connected and data.corners is not None)


class LevelMateTemperatureSensor(_LevelMateBaseSensor):
    _attr_name = "Temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: LevelMateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data['address']}_temperature"

    @property
    def native_value(self) -> float | None:
        data: LevelMateData = self.coordinator.data
        return data.temperature_c if data else None


class LevelMateRawSideSensor(_LevelMateBaseSensor):
    """Diagnostic: raw _side reading in inches (not corner-relative)."""

    _attr_name = "Raw Side Reading"
    _attr_native_unit_of_measurement = "in"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:axis-y-arrow"

    def __init__(self, coordinator: LevelMateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data['address']}_raw_side"

    @property
    def native_value(self) -> float | None:
        data: LevelMateData = self.coordinator.data
        if not data or data.side_raw is None:
            return None
        from .const import INCHES_PER_RAW_COUNT

        return round(data.side_raw * INCHES_PER_RAW_COUNT, 4)


class LevelMateRawFrontSensor(_LevelMateBaseSensor):
    """Diagnostic: raw _front reading in inches (not corner-relative)."""

    _attr_name = "Raw Front Reading"
    _attr_native_unit_of_measurement = "in"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:axis-x-arrow"

    def __init__(self, coordinator: LevelMateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data['address']}_raw_front"

    @property
    def native_value(self) -> float | None:
        data: LevelMateData = self.coordinator.data
        if not data or data.front_raw is None:
            return None
        from .const import INCHES_PER_RAW_COUNT

        return round(data.front_raw * INCHES_PER_RAW_COUNT, 4)
