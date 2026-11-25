"""A configured irlingo remote: encoding and sending its codes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.components.infrared import InfraredCommand, InfraredEmitterConsumerEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

from .const import DEFAULT_FREQUENCY, DOMAIN, MODE_GUESSES
from .encoder import EncodeError, Remote


class IrlingoCommand(InfraredCommand):
    """A code irlingo encoded, as raw timings for any infrared emitter."""

    def __init__(self, timings: list[int], modulation: int) -> None:
        """Pulses positive, spaces negative, in microseconds; modulation in Hz."""
        super().__init__(modulation=modulation)
        self._timings = timings

    def get_raw_timings(self) -> list[int]:
        """The timings of the code."""
        return list(self._timings)


@dataclass
class ClimateMapping:
    """How a remote's features become a climate entity."""

    # Home Assistant HVAC mode: the features sent for it
    modes: dict[str, dict[str, str]]
    temperature: str | None = None
    # (degrees, the feature value), sorted
    temperatures: list[tuple[float, str]] = field(default_factory=list)
    fan: str | None = None
    fan_values: list[str] = field(default_factory=list)


def _number(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def climate_mapping(remote: Remote) -> ClimateMapping | None:
    """The climate entity of an air conditioner remote, guessed from its feature
    names (mode, power, temperature, fan) as the ESPHome component does; None
    when the remote has no mode feature with values like HEAT or COOL."""
    features = remote.features
    modes: dict[str, dict[str, str]] = {}
    for value in features.get("mode", {}):
        mode = MODE_GUESSES.get(value.upper())
        if mode and mode not in modes:
            modes[mode] = {"mode": value}
    power = features.get("power", {})
    if modes and "ON" in power and "OFF" in power:
        for values in modes.values():
            values["power"] = "ON"
        modes["off"] = {"power": "OFF"}
    if not modes:
        return None

    mapping = ClimateMapping(modes)
    if "temperature" in features:
        temperatures = sorted(
            (number, value) for value in features["temperature"] if (number := _number(value)) is not None
        )
        if temperatures:
            mapping.temperature = "temperature"
            mapping.temperatures = temperatures
    if "fan" in features:
        mapping.fan = "fan"
        mapping.fan_values = list(features["fan"])
    return mapping


class IrlingoDevice:
    """A remote sent through an infrared emitter. Remotes with a toggle bit send
    another code every other press; which one is next survives restarts."""

    def __init__(self, hass: HomeAssistant, entry_id: str, remote: Remote, emitter: str) -> None:
        """Use a loaded remote and the emitter entity to send it through."""
        self.hass = hass
        self.remote = remote
        self.emitter = emitter
        self.toggled = False
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry_id}")

    async def async_load(self) -> None:
        """Restore the toggle state."""
        if self.remote.has_toggle and (data := await self._store.async_load()):
            self.toggled = bool(data.get("toggled", False))

    def command(self, features: dict[str, str]) -> IrlingoCommand:
        """The command for these feature values."""
        for name, value in features.items():
            if not self.remote.has_feature(name, value):
                raise HomeAssistantError(f"Remote {self.remote.name} has no feature {name}={value}")
        try:
            code = self.remote.encode(features, self.toggled)
            timings = self.remote.timings(code)
        except EncodeError as err:
            raise HomeAssistantError(f"Remote {self.remote.name}: {err}") from err
        return IrlingoCommand(timings, self.remote.frequency or DEFAULT_FREQUENCY)

    async def async_send(self, entity: InfraredEmitterConsumerEntity, features: dict[str, str]) -> None:
        """Send the code for these feature values through the entity's emitter."""
        command = self.command(features)
        await entity._send_command(command)  # noqa: SLF001
        if self.remote.has_toggle:
            self.toggled = not self.toggled
            self._store.async_delay_save(lambda: {"toggled": self.toggled}, 1)
