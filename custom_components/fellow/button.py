"""Button platform for Stagg EKG integration."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
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
    """Set up Stagg EKG buttons."""
    coordinator: StaggEKGDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([StaggEKGEmergencyStopButton(coordinator, entry)])


class StaggEKGEmergencyStopButton(CoordinatorEntity, ButtonEntity):
    """Kill switch: turn the heater and warmer off, whatever the mode says."""

    def __init__(
        self, coordinator: StaggEKGDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{entry.entry_id}_emergency_stop"
        self._attr_name = "Emergency Stop"
        self._attr_icon = "mdi:stop-circle"

    @property
    def available(self) -> bool:
        """Always pressable, even when polling is failing."""
        return True

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

    async def async_press(self) -> None:
        """Send the emergency stop, then refresh so the UI shows the result."""
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.client.emergency_stop
            )
        finally:
            await self.coordinator.async_request_refresh()
