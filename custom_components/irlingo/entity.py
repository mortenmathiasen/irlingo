"""The base of irlingo's entities: one device per configured remote."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

if TYPE_CHECKING:
    from . import IrlingoConfigEntry


class IrlingoEntity(InfraredEmitterConsumerEntity):
    """An entity sending a remote's codes; unavailable while its emitter is."""

    _attr_has_entity_name = True
    _attr_assumed_state = True

    def __init__(self, entry: IrlingoConfigEntry, key: str | None = None) -> None:
        """The entity of entry; key tells apart several entities of one remote."""
        self.device = entry.runtime_data
        self._infrared_emitter_entity_id = self.device.emitter
        self._attr_unique_id = entry.entry_id if key is None else f"{entry.entry_id}_{key}"
        manufacturer, _, model = self.device.remote.name.partition("/")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=manufacturer.replace("_", " ").title(),
            model=model,
        )
