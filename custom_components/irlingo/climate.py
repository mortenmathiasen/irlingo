"""The climate entity of an air conditioner remote.

Every change sends one code with the features of the mode, the target
temperature (the remote's nearest value) and the fan speed, as the ESPHome
component does. The remote's fan value AUTO becomes Home Assistant's "auto";
its other values are offered by name. The state is assumed: the last one sent,
restored after a restart without sending it.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    FAN_AUTO,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import IrlingoConfigEntry
from .device import ClimateMapping, climate_mapping
from .entity import IrlingoEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: IrlingoConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Add the climate entity of an air conditioner remote."""
    if (mapping := climate_mapping(entry.runtime_data.remote)) is not None:
        async_add_entities([IrlingoClimate(entry, mapping)])


def _fan_mode(value: str) -> str:
    return FAN_AUTO if value.upper() == "AUTO" else value


class IrlingoClimate(IrlingoEntity, ClimateEntity, RestoreEntity):
    """An air conditioner controlled by its infrared remote."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, entry: IrlingoConfigEntry, mapping: ClimateMapping) -> None:
        """The climate entity of entry."""
        super().__init__(entry)
        self.mapping = mapping
        self._attr_hvac_modes = [HVACMode(mode) for mode in mapping.modes]
        features = ClimateEntityFeature(0)
        if HVACMode.OFF in self._attr_hvac_modes and len(self._attr_hvac_modes) > 1:
            features |= ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        if mapping.temperatures:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
            self._attr_min_temp = mapping.temperatures[0][0]
            self._attr_max_temp = mapping.temperatures[-1][0]
            whole = all(number == int(number) for number, _ in mapping.temperatures)
            self._attr_target_temperature_step = 1.0 if whole else 0.5
            self._attr_target_temperature = self._nearest(21.0)[0]
        self._fan_values = {_fan_mode(value): value for value in mapping.fan_values}
        if self._fan_values:
            features |= ClimateEntityFeature.FAN_MODE
            self._attr_fan_modes = list(self._fan_values)
            self._attr_fan_mode = FAN_AUTO if FAN_AUTO in self._fan_values else self._attr_fan_modes[0]
        self._attr_supported_features = features
        self._attr_hvac_mode = HVACMode.OFF if HVACMode.OFF in self._attr_hvac_modes else self._attr_hvac_modes[0]
        self._last_on_mode = next((m for m in self._attr_hvac_modes if m != HVACMode.OFF), None)

    def _nearest(self, temperature: float) -> tuple[float, str]:
        """The remote's temperature value nearest to temperature."""
        return min(self.mapping.temperatures, key=lambda entry: abs(entry[0] - temperature))

    async def async_added_to_hass(self) -> None:
        """Restore the last state without sending it: a restart must not switch
        the air conditioner."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is None:
            return
        if state.state in self._attr_hvac_modes:
            self._attr_hvac_mode = HVACMode(state.state)
            if self._attr_hvac_mode != HVACMode.OFF:
                self._last_on_mode = self._attr_hvac_mode
        if self.mapping.temperatures and (temperature := state.attributes.get(ATTR_TEMPERATURE)) is not None:
            self._attr_target_temperature = self._nearest(float(temperature))[0]
        if state.attributes.get(ATTR_FAN_MODE) in self._fan_values:
            self._attr_fan_mode = state.attributes[ATTR_FAN_MODE]

    async def _async_send_state(self) -> None:
        """Send the code for the current mode, temperature and fan speed."""
        features = dict(self.mapping.modes[self._attr_hvac_mode])
        if self.mapping.temperature is not None and self._attr_target_temperature is not None:
            number, value = self._nearest(self._attr_target_temperature)
            self._attr_target_temperature = number
            features[self.mapping.temperature] = value
        if self.mapping.fan is not None and self._attr_fan_mode in self._fan_values:
            features[self.mapping.fan] = self._fan_values[self._attr_fan_mode]
        await self.device.async_send(self, features)
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Switch to a mode."""
        self._attr_hvac_mode = hvac_mode
        if hvac_mode != HVACMode.OFF:
            self._last_on_mode = hvac_mode
        await self._async_send_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature, and the mode when given."""
        if (mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            self._attr_hvac_mode = HVACMode(mode)
            if self._attr_hvac_mode != HVACMode.OFF:
                self._last_on_mode = self._attr_hvac_mode
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None and self.mapping.temperatures:
            self._attr_target_temperature = self._nearest(float(temperature))[0]
        await self._async_send_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan speed."""
        self._attr_fan_mode = fan_mode
        await self._async_send_state()

    async def async_turn_on(self) -> None:
        """Switch on in the last mode used."""
        if self._last_on_mode is not None:
            await self.async_set_hvac_mode(self._last_on_mode)

    async def async_turn_off(self) -> None:
        """Switch off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
