"""Tests for the Scheduled Restart integration setup and services."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.scheduled_restart.const import (
    CONF_RESTART_DAYS,
    CONF_RESTART_TIME,
    DOMAIN,
    NOTIFICATION_ID,
    SERVICE_CANCEL_RESTART,
    SERVICE_REQUEST_RESTART,
    SIGNAL_RESTART_STATE_CHANGED,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_loads_pending_state_from_store(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a pending restart state is restored from the store on setup."""
    with patch(
        "homeassistant.components.scheduled_restart.Store.async_load",
        return_value={"restart_pending": True, "restart_reason": "update required"},
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    runtime_data = mock_config_entry.runtime_data
    assert runtime_data.restart_pending is True
    assert runtime_data.restart_reason == "update required"


async def test_request_restart_service(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the request_restart service marks the restart as pending."""
    runtime_data = init_integration.runtime_data
    assert runtime_data.restart_pending is False

    with patch.object(runtime_data.store, "async_save", return_value=None) as mock_save:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REQUEST_RESTART,
            {"reason": "test reason"},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert runtime_data.restart_pending is True
    assert runtime_data.restart_reason == "test reason"
    mock_save.assert_called_once_with(
        {"restart_pending": True, "restart_reason": "test reason"}
    )


async def test_request_restart_without_reason(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the request_restart service works without an optional reason."""
    runtime_data = init_integration.runtime_data

    with patch.object(runtime_data.store, "async_save", return_value=None):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REQUEST_RESTART,
            blocking=True,
        )
        await hass.async_block_till_done()

    assert runtime_data.restart_pending is True
    assert runtime_data.restart_reason is None


async def test_cancel_restart_service(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the cancel_restart service clears the pending restart."""
    runtime_data = init_integration.runtime_data
    runtime_data.restart_pending = True
    runtime_data.restart_reason = "some reason"

    with patch.object(runtime_data.store, "async_save", return_value=None) as mock_save:
        await hass.services.async_call(
            DOMAIN, SERVICE_CANCEL_RESTART, blocking=True
        )
        await hass.async_block_till_done()

    assert runtime_data.restart_pending is False
    assert runtime_data.restart_reason is None
    mock_save.assert_called_once_with({"restart_pending": False, "restart_reason": None})


async def test_cancel_restart_raises_when_not_pending(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test cancel_restart raises ServiceValidationError when nothing is pending."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, SERVICE_CANCEL_RESTART, blocking=True
        )


async def test_scheduled_restart_fires_at_configured_time(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that Home Assistant restarts when time is reached and a restart is pending."""
    runtime_data = init_integration.runtime_data
    runtime_data.restart_pending = True
    runtime_data.restart_reason = "scheduled"

    restart_called = False

    async def mock_restart(*args, **kwargs) -> None:
        nonlocal restart_called
        restart_called = True

    with (
        patch.object(runtime_data.store, "async_save", return_value=None),
        patch.object(hass.services, "async_call", side_effect=mock_restart),
    ):
        # Fire time matching the configured "02:00:00"
        fire_time = dt_util.now().replace(hour=2, minute=0, second=0, microsecond=0)
        async_fire_time_changed(hass, fire_time)
        await hass.async_block_till_done()

    assert restart_called
    assert runtime_data.restart_pending is False


async def test_scheduled_restart_skips_non_configured_day(
    hass: HomeAssistant,
) -> None:
    """Test that the restart is skipped on a day not in the configured days list."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Scheduled Restart",
        data={
            CONF_RESTART_TIME: "02:00:00",
            CONF_RESTART_DAYS: ["mon"],  # Only Monday
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    runtime_data = entry.runtime_data
    runtime_data.restart_pending = True

    restart_called = False

    async def mock_restart(*args, **kwargs) -> None:
        nonlocal restart_called
        restart_called = True

    with patch.object(hass.services, "async_call", side_effect=mock_restart):
        # Fire time on a Tuesday (weekday index 1)
        tuesday = dt_util.now()
        # Advance to next Tuesday
        days_ahead = (1 - tuesday.weekday()) % 7 or 7
        fire_time = tuesday.replace(
            hour=2, minute=0, second=0, microsecond=0
        )
        # Manually override weekday for the test by using a known Tuesday
        fire_time = datetime(2024, 1, 2, 2, 0, 0, tzinfo=dt_util.get_default_time_zone())
        async_fire_time_changed(hass, fire_time)
        await hass.async_block_till_done()

    assert not restart_called
    # Pending flag should remain set since we didn't restart
    assert runtime_data.restart_pending is True


async def test_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that the config entry unloads cleanly."""
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state.name == "NOT_LOADED"


async def test_options_update_resets_time_listener(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test that updating options re-registers the time listener."""
    entry = init_integration
    runtime_data = entry.runtime_data
    original_cancel = runtime_data._cancel_listener

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_RESTART_TIME: "05:00:00",
            CONF_RESTART_DAYS: ["sat"],
        },
    )
    await hass.async_block_till_done()

    # A new listener should have been registered (different callable)
    assert runtime_data._cancel_listener is not original_cancel
