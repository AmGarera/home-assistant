"""Binary sensor platform for the Scheduled Restart integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ScheduledRestartConfigEntry
from .const import DOMAIN, SIGNAL_RESTART_STATE_CHANGED


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ScheduledRestartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Scheduled Restart binary sensors from a config entry."""
    async_add_entities([ScheduledRestartPendingSensor(entry)])


class ScheduledRestartPendingSensor(BinarySensorEntity):
    """Binary sensor indicating whether a restart is pending."""

    _attr_has_entity_name = True
    _attr_translation_key = "restart_pending"

    def __init__(self, entry: ScheduledRestartConfigEntry) -> None:
        """Initialize the sensor."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_restart_pending"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Scheduled Restart",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def is_on(self) -> bool:
        """Return true when a restart is pending."""
        return self._entry.runtime_data.restart_pending

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {"reason": self._entry.runtime_data.restart_reason}

    async def async_added_to_hass(self) -> None:
        """Subscribe to dispatcher signals when added to Home Assistant."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_RESTART_STATE_CHANGED,
                self._handle_state_change,
            )
        )

    @callback
    def _handle_state_change(self) -> None:
        """Update the entity state when the pending flag changes."""
        self.async_write_ha_state()
