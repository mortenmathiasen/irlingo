"""Buttons: one for each key of a remote."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IrlingoConfigEntry
from .entity import IrlingoEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: IrlingoConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Add a button for each value of the remote's key feature."""
    keys = entry.runtime_data.remote.features.get("key", {})
    async_add_entities(IrlingoButton(entry, key) for key in keys)


class IrlingoButton(IrlingoEntity, ButtonEntity):
    """Sends one key of the remote."""

    def __init__(self, entry: IrlingoConfigEntry, key: str) -> None:
        """The button for a key, e.g. KEY_POWER."""
        super().__init__(entry, f"key_{key}")
        self._key = key
        self._attr_name = key

    async def async_press(self) -> None:
        """Send the key."""
        await self.device.async_send(self, {"key": self._key})
