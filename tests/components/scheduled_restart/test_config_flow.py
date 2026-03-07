"""Tests for the Scheduled Restart config flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.scheduled_restart.const import (
    CONF_RESTART_DAYS,
    CONF_RESTART_TIME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import WEEKDAYS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """Test the user flow creates an entry with provided configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_RESTART_TIME: "03:00:00",
            CONF_RESTART_DAYS: ["mon", "wed", "fri"],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Scheduled Restart"
    assert result["data"][CONF_RESTART_TIME] == "03:00:00"
    assert result["data"][CONF_RESTART_DAYS] == ["mon", "wed", "fri"]


async def test_single_config_entry_abort(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a second config entry is aborted."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_updates_config(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the options flow updates the configuration."""
    entry = init_integration

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_RESTART_TIME: "04:30:00",
            CONF_RESTART_DAYS: ["sat", "sun"],
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_RESTART_TIME] == "04:30:00"
    assert entry.options[CONF_RESTART_DAYS] == ["sat", "sun"]


async def test_options_flow_preserves_current_values(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the options flow pre-fills with current configuration values."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert result["type"] is FlowResultType.FORM

    schema_keys = {str(key) for key in result["data_schema"].schema}
    assert CONF_RESTART_TIME in schema_keys
    assert CONF_RESTART_DAYS in schema_keys
