"""Sensor platform for Stagg EKG integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import StaggEKGDataUpdateCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Stagg EKG sensors."""
    coordinator: StaggEKGDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        StaggEKGCurrentTempSensor(coordinator, entry),
        StaggEKGTargetTempSensor(coordinator, entry),
        StaggEKGModeSensor(coordinator, entry),
        StaggEKGRawStatusSensor(coordinator, entry),
    ]

    async_add_entities(entities)


class StaggEKGSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Stagg EKG sensors."""

    def __init__(
        self, coordinator: StaggEKGDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_has_entity_name = True

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Stagg EKG+",
            "manufacturer": "Fellow",
            "model": "Stagg EKG+",
            "sw_version": "1.1.76SSP",
        }


class StaggEKGCurrentTempSensor(StaggEKGSensorBase):
    """Current temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self, coordinator: StaggEKGDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_current_temp"
        self._attr_name = "Current Temperature"

    @property
    def native_value(self) -> float | None:
        """Return the current temperature."""
        if self.coordinator.data and "state" in self.coordinator.data:
            return self.coordinator.data["state"].current_temp_c
        return None


class StaggEKGTargetTempSensor(StaggEKGSensorBase):
    """Target temperature sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self, coordinator: StaggEKGDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_target_temp"
        self._attr_name = "Target Temperature"

    @property
    def native_value(self) -> float | None:
        """Return the target temperature."""
        if self.coordinator.data and "state" in self.coordinator.data:
            return self.coordinator.data["state"].set_temp_c
        return None


class StaggEKGModeSensor(StaggEKGSensorBase):
    """Kettle mode sensor."""

    def __init__(
        self, coordinator: StaggEKGDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_mode"
        self._attr_name = "Mode"

    @property
    def icon(self) -> str:
        """Steam the kettle icon while it's actively heating."""
        if self.coordinator.data and "state" in self.coordinator.data:
            if self.coordinator.data["state"].is_heating:
                return "mdi:kettle-steam"
        return "mdi:kettle"

    @property
    def native_value(self) -> str | None:
        """Return the kettle mode."""
        if self.coordinator.data and "state" in self.coordinator.data:
            mode = self.coordinator.data["state"].mode
            # Clean up mode name
            if mode.startswith("S_"):
                mode = mode[2:]
            return mode
        return None


class StaggEKGRawStatusSensor(StaggEKGSensorBase):
    """What the kettle's `state` command returned on the latest poll.

    For debugging: the state is the mode and the unrounded temperature, and
    the full response is in the `raw` attribute (kept out of the recorder,
    since it changes every poll).
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _unrecorded_attributes = frozenset({"raw"})

    def __init__(
        self, coordinator: StaggEKGDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_raw_status"
        self._attr_name = "Raw Status"
        self._attr_icon = "mdi:console"

    @property
    def native_value(self) -> str | None:
        """Return the mode and temperature, e.g. "S_Heat 74.280831 C"."""
        if not (self.coordinator.data and "state" in self.coordinator.data):
            return None
        state = self.coordinator.data["state"]
        temp = "nan" if state.current_temp_c is None else repr(state.current_temp_c)
        return f"{state.mode} {temp} C"

    @property
    def extra_state_attributes(self):
        """Return the parsed fields and the raw response."""
        if not (self.coordinator.data and "state" in self.coordinator.data):
            return {}
        state = self.coordinator.data["state"]
        return {
            "mode": state.mode,
            "temperature": state.current_temp_c,
            "target_temperature": state.set_temp_c,
            "screen": state.screen_name,
            "clock": state.clock,
            "last_poll": self.coordinator.last_poll,
            "raw": state.raw,
        }
