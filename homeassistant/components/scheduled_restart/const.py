"""Constants for the Scheduled Restart integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "scheduled_restart"

PLATFORMS: Final = [Platform.BINARY_SENSOR]

CONF_RESTART_TIME: Final = "restart_time"
CONF_RESTART_DAYS: Final = "restart_days"

SERVICE_REQUEST_RESTART: Final = "request_restart"
SERVICE_CANCEL_RESTART: Final = "cancel_restart"

ATTR_REASON: Final = "reason"

STORAGE_KEY: Final = DOMAIN
STORAGE_VERSION: Final = 1

NOTIFICATION_ID: Final = f"{DOMAIN}_pending"

SIGNAL_RESTART_STATE_CHANGED: Final = f"{DOMAIN}_state_changed"
