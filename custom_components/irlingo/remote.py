"""The remote entity: remote.send_command with a remote's feature values."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from homeassistant.components.remote import ATTR_DELAY_SECS, ATTR_NUM_REPEATS, RemoteEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IrlingoConfigEntry
from .entity import IrlingoEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: IrlingoConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Add the remote entity."""
    async_add_entities([IrlingoRemoteEntity(entry)])


class IrlingoRemoteEntity(IrlingoEntity, RemoteEntity):
    """Sends commands such as KEY_POWER, or feature values such as
    "mode=HEAT temperature=21"."""

    _attr_translation_key = "remote"

    def __init__(self, entry: IrlingoConfigEntry) -> None:
        """The remote entity of entry."""
        super().__init__(entry, "remote")

    def features_of(self, command: str) -> dict[str, str]:
        """The feature values a command stands for: NAME=VALUE pairs separated by
        spaces or commas, or a value of one of the remote's features, e.g. a key."""
        remote = self.device.remote
        parts = command.replace(",", " ").split()
        if parts and all("=" in part for part in parts):
            return dict(part.split("=", 1) for part in parts)
        for name, values in remote.features.items():
            if command in values:
                return {name: command}
        raise ServiceValidationError(f"Remote {remote.name} has no command {command}")

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send each command num_repeats times, delay_secs apart."""
        commands = [self.features_of(item) for item in command]
        repeats = kwargs.get(ATTR_NUM_REPEATS, 1)
        delay = kwargs.get(ATTR_DELAY_SECS, 0.4)
        first = True
        for _ in range(repeats):
            for features in commands:
                if not first and delay:
                    await asyncio.sleep(delay)
                first = False
                await self.device.async_send(self, features)
