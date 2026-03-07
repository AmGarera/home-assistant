"""Config flow for the Scheduled Restart integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import WEEKDAYS
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_RESTART_DAYS, CONF_RESTART_TIME, DOMAIN

_DEFAULT_RESTART_TIME = "02:00:00"
_WEEKDAY_OPTIONS = [
    selector.SelectOptionDict(value=day, label=day.capitalize()) for day in WEEKDAYS
]


def _build_schema(
    restart_time: str = _DEFAULT_RESTART_TIME,
    restart_days: list[str] | None = None,
) -> vol.Schema:
    """Build the configuration schema with current defaults."""
    if restart_days is None:
        restart_days = list(WEEKDAYS)
    return vol.Schema(
        {
            vol.Required(CONF_RESTART_TIME, default=restart_time): selector.TimeSelector(),
            vol.Optional(CONF_RESTART_DAYS, default=restart_days): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_WEEKDAY_OPTIONS,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        }
    )


class ScheduledRestartConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Scheduled Restart."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Scheduled Restart", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: Any,
    ) -> ScheduledRestartOptionsFlow:
        """Return the options flow handler."""
        return ScheduledRestartOptionsFlow()


class ScheduledRestartOptionsFlow(OptionsFlow):
    """Handle options for Scheduled Restart."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_time = self.config_entry.options.get(
            CONF_RESTART_TIME,
            self.config_entry.data.get(CONF_RESTART_TIME, _DEFAULT_RESTART_TIME),
        )
        current_days = self.config_entry.options.get(
            CONF_RESTART_DAYS,
            self.config_entry.data.get(CONF_RESTART_DAYS, list(WEEKDAYS)),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(current_time, current_days),
        )
