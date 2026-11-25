"""Config flow: a remote, chosen by manufacturer, and the infrared emitter to send it through."""

from __future__ import annotations

from typing import Any

from homeassistant.components.infrared import DOMAIN as INFRARED_DOMAIN, async_get_emitters
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
import voluptuous as vol

from .const import CONF_INFRARED_EMITTER_ENTITY_ID, CONF_MANUFACTURER, CONF_REMOTE, DOMAIN
from .encoder import EncodeError
from .remotes import load_remote, manufacturers, remotes_of


class IrlingoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a remote."""

    VERSION = 1

    def __init__(self) -> None:
        """Start the flow."""
        self._manufacturer: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose the manufacturer."""
        if not async_get_emitters(self.hass):
            return self.async_abort(reason="no_infrared_emitters")
        options = await self.hass.async_add_executor_job(manufacturers)
        if user_input is not None and user_input[CONF_MANUFACTURER] in options:
            self._manufacturer = user_input[CONF_MANUFACTURER]
            return await self.async_step_remote()
        schema = vol.Schema(
            {
                vol.Required(CONF_MANUFACTURER): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN, sort=False)
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_remote(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose the remote, the emitter and the name."""
        assert self._manufacturer is not None
        options = await self.hass.async_add_executor_job(remotes_of, self._manufacturer)
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_REMOTE]
            try:
                remote = await self.hass.async_add_executor_job(load_remote, name)
            except EncodeError:
                errors[CONF_REMOTE] = "cannot_load"
            else:
                if not remote.features:
                    errors[CONF_REMOTE] = "cannot_load"
            if name not in options:
                errors[CONF_REMOTE] = "cannot_load"
            if not errors:
                title = user_input.get(CONF_NAME) or name
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_REMOTE: name,
                        CONF_INFRARED_EMITTER_ENTITY_ID: user_input[CONF_INFRARED_EMITTER_ENTITY_ID],
                    },
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_REMOTE): SelectSelector(
                    SelectSelectorConfig(
                        options=[{"value": name, "label": name.split("/", 1)[1]} for name in options],
                        mode=SelectSelectorMode.DROPDOWN,
                        sort=False,
                    )
                ),
                vol.Required(CONF_INFRARED_EMITTER_ENTITY_ID): EntitySelector(
                    EntitySelectorConfig(domain=INFRARED_DOMAIN, include_entities=async_get_emitters(self.hass))
                ),
                vol.Optional(CONF_NAME): TextSelector(),
            }
        )
        return self.async_show_form(
            step_id="remote",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
            description_placeholders={"manufacturer": self._manufacturer},
        )
