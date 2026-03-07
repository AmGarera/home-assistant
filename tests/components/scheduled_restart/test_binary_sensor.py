"""Tests for the Scheduled Restart binary sensor."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.scheduled_restart.const import (
    DOMAIN,
    SERVICE_CANCEL_RESTART,
    SERVICE_REQUEST_RESTART,
    SIGNAL_RESTART_STATE_CHANGED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import MockConfigEntry


async def test_binary_sensor_initial_state_is_off(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that the binary sensor starts in the off (not pending) state."""
    state = hass.states.get("binary_sensor.scheduled_restart_restart_pending")
    assert state is not None
    assert state.state == "off"


async def test_binary_sensor_turns_on_when_restart_requested(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that the binary sensor turns on after a restart is requested."""
    runtime_data = init_integration.runtime_data

    with patch.object(runtime_data.store, "async_save", return_value=None):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REQUEST_RESTART,
            {"reason": "firmware update"},
            blocking=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.scheduled_restart_restart_pending")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["reason"] == "firmware update"


async def test_binary_sensor_turns_off_after_cancel(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that the binary sensor returns to off after a restart is cancelled."""
    runtime_data = init_integration.runtime_data
    runtime_data.restart_pending = True
    runtime_data.restart_reason = "test"

    async_dispatcher_send(hass, SIGNAL_RESTART_STATE_CHANGED)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.scheduled_restart_restart_pending")
    assert state.state == "on"

    with patch.object(runtime_data.store, "async_save", return_value=None):
        await hass.services.async_call(
            DOMAIN, SERVICE_CANCEL_RESTART, blocking=True
        )
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.scheduled_restart_restart_pending")
    assert state.state == "off"
    assert state.attributes["reason"] is None


async def test_binary_sensor_has_correct_device(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test that the binary sensor is associated with the correct device."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    entry = entity_registry.async_get(
        "binary_sensor.scheduled_restart_restart_pending"
    )
    assert entry is not None
    assert entry.unique_id == f"{init_integration.entry_id}_restart_pending"

    device = device_registry.async_get(entry.device_id)
    assert device is not None
    assert (DOMAIN, init_integration.entry_id) in device.identifiers
