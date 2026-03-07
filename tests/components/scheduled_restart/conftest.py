"""Fixtures for Scheduled Restart integration tests."""

from __future__ import annotations

import pytest

from homeassistant.components.scheduled_restart.const import CONF_RESTART_DAYS, CONF_RESTART_TIME, DOMAIN
from homeassistant.const import WEEKDAYS

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Scheduled Restart",
        data={
            CONF_RESTART_TIME: "02:00:00",
            CONF_RESTART_DAYS: list(WEEKDAYS),
        },
        unique_id=None,
    )


@pytest.fixture
async def init_integration(
    hass,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
