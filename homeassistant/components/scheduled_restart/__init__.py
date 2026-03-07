"""Integration for scheduling Home Assistant restarts."""

from __future__ import annotations

from collections.abc import Callable
import datetime
from dataclasses import dataclass, field
import logging

import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import WEEKDAYS
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_REASON,
    CONF_RESTART_DAYS,
    CONF_RESTART_TIME,
    DOMAIN,
    NOTIFICATION_ID,
    PLATFORMS,
    SERVICE_CANCEL_RESTART,
    SERVICE_REQUEST_RESTART,
    SIGNAL_RESTART_STATE_CHANGED,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

type ScheduledRestartConfigEntry = ConfigEntry[ScheduledRestartRuntimeData]


@dataclass
class ScheduledRestartRuntimeData:
    """Runtime data for the Scheduled Restart integration."""

    store: Store
    restart_pending: bool
    restart_reason: str | None
    _cancel_listener: Callable[[], None] | None = field(default=None, repr=False)

    def cancel_time_listener(self) -> None:
        """Cancel the active time change listener."""
        if self._cancel_listener is not None:
            self._cancel_listener()
            self._cancel_listener = None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Scheduled Restart services."""

    async def _handle_request_restart(call: ServiceCall) -> None:
        """Handle the request_restart service call."""
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_config_entry",
            )

        entry = entries[0]
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="integration_not_loaded",
            )

        runtime_data: ScheduledRestartRuntimeData = entry.runtime_data
        reason = call.data.get(ATTR_REASON)

        runtime_data.restart_pending = True
        runtime_data.restart_reason = reason

        await runtime_data.store.async_save(
            {"restart_pending": True, "restart_reason": reason}
        )

        restart_time = entry.options.get(
            CONF_RESTART_TIME, entry.data[CONF_RESTART_TIME]
        )
        _LOGGER.info(
            "Restart scheduled for %s (reason: %s)",
            restart_time,
            reason or "not specified",
        )

        persistent_notification.async_create(
            hass,
            (
                f"Home Assistant will restart at **{restart_time}**."
                f"\n\nReason: {reason or 'not specified'}."
                "\n\nTo cancel, call the `scheduled_restart.cancel_restart` service."
            ),
            "Restart scheduled",
            NOTIFICATION_ID,
        )

        async_dispatcher_send(hass, SIGNAL_RESTART_STATE_CHANGED)

    async def _handle_cancel_restart(call: ServiceCall) -> None:
        """Handle the cancel_restart service call."""
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_config_entry",
            )

        entry = entries[0]
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="integration_not_loaded",
            )

        runtime_data: ScheduledRestartRuntimeData = entry.runtime_data
        if not runtime_data.restart_pending:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_restart_pending",
            )

        runtime_data.restart_pending = False
        runtime_data.restart_reason = None

        await runtime_data.store.async_save(
            {"restart_pending": False, "restart_reason": None}
        )

        persistent_notification.async_dismiss(hass, NOTIFICATION_ID)
        _LOGGER.info("Scheduled restart cancelled")

        async_dispatcher_send(hass, SIGNAL_RESTART_STATE_CHANGED)

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_REQUEST_RESTART,
        _handle_request_restart,
        vol.Schema({vol.Optional(ATTR_REASON): cv.string}),
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_CANCEL_RESTART,
        _handle_cancel_restart,
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ScheduledRestartConfigEntry
) -> bool:
    """Set up Scheduled Restart from a config entry."""
    store: Store[dict] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored_data = await store.async_load() or {}

    runtime_data = ScheduledRestartRuntimeData(
        store=store,
        restart_pending=stored_data.get("restart_pending", False),
        restart_reason=stored_data.get("restart_reason"),
    )
    entry.runtime_data = runtime_data

    _setup_time_listener(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


@callback
def _setup_time_listener(
    hass: HomeAssistant, entry: ScheduledRestartConfigEntry
) -> None:
    """Register the daily time listener for the configured restart time."""
    runtime_data = entry.runtime_data
    runtime_data.cancel_time_listener()

    restart_time_str = entry.options.get(
        CONF_RESTART_TIME, entry.data[CONF_RESTART_TIME]
    )
    # TimeSelector yields "HH:MM:SS"
    time_parts = restart_time_str.split(":")
    hour = int(time_parts[0])
    minute = int(time_parts[1])
    second = int(time_parts[2]) if len(time_parts) > 2 else 0

    @callback
    def _async_restart_time_reached(now: datetime.datetime) -> None:
        """Handle the configured restart time being reached each day."""
        if not entry.runtime_data.restart_pending:
            return

        restart_days: list[str] = entry.options.get(
            CONF_RESTART_DAYS,
            entry.data.get(CONF_RESTART_DAYS, WEEKDAYS),
        )
        current_day = WEEKDAYS[now.weekday()]
        if current_day not in restart_days:
            _LOGGER.debug(
                "Skipping scheduled restart: today (%s) is not in configured days %s",
                current_day,
                restart_days,
            )
            return

        _LOGGER.info(
            "Initiating scheduled restart (reason: %s)",
            entry.runtime_data.restart_reason or "not specified",
        )
        hass.async_create_task(
            _async_perform_restart(hass, entry),
            name=f"{DOMAIN}_restart",
        )

    cancel = async_track_time_change(
        hass,
        _async_restart_time_reached,
        hour=hour,
        minute=minute,
        second=second,
    )
    runtime_data._cancel_listener = cancel


async def _async_perform_restart(
    hass: HomeAssistant, entry: ScheduledRestartConfigEntry
) -> None:
    """Clear the pending state and restart Home Assistant."""
    runtime_data = entry.runtime_data

    # Clear the flag before restarting so it won't trigger again after boot.
    runtime_data.restart_pending = False
    runtime_data.restart_reason = None
    await runtime_data.store.async_save(
        {"restart_pending": False, "restart_reason": None}
    )

    persistent_notification.async_dismiss(hass, NOTIFICATION_ID)
    async_dispatcher_send(hass, SIGNAL_RESTART_STATE_CHANGED)

    await hass.services.async_call(
        "homeassistant",
        "restart",
        blocking=False,
    )


async def _async_update_listener(
    hass: HomeAssistant, entry: ScheduledRestartConfigEntry
) -> None:
    """Handle option updates by resetting the time listener."""
    _setup_time_listener(hass, entry)


async def async_unload_entry(
    hass: HomeAssistant, entry: ScheduledRestartConfigEntry
) -> bool:
    """Unload a config entry."""
    entry.runtime_data.cancel_time_listener()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
