"""irlingo: send thousands of infrared remotes through any infrared emitter.

Each config entry is one remote (e.g. a TV or an air conditioner) sent through
one of Home Assistant's infrared emitters (ESPHome, Broadlink, ...). Air
conditioners become climate entities; remotes with keys get buttons and a
remote entity for remote.send_command.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import CONF_INFRARED_EMITTER_ENTITY_ID, CONF_REMOTE
from .device import IrlingoDevice, climate_mapping
from .encoder import EncodeError
from .remotes import load_remote

type IrlingoConfigEntry = ConfigEntry[IrlingoDevice]


def platforms_for(device: IrlingoDevice) -> list[Platform]:
    """The entities a remote gets."""
    platforms = [Platform.REMOTE]
    if climate_mapping(device.remote) is not None:
        platforms.append(Platform.CLIMATE)
    if "key" in device.remote.features:
        platforms.append(Platform.BUTTON)
    return platforms


async def async_setup_entry(hass: HomeAssistant, entry: IrlingoConfigEntry) -> bool:
    """Set up a remote."""
    try:
        remote = await hass.async_add_executor_job(load_remote, entry.data[CONF_REMOTE])
    except EncodeError as err:
        raise ConfigEntryError(str(err)) from err
    device = IrlingoDevice(hass, entry.entry_id, remote, entry.data[CONF_INFRARED_EMITTER_ENTITY_ID])
    await device.async_load()
    entry.runtime_data = device
    await hass.config_entries.async_forward_entry_setups(entry, platforms_for(device))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IrlingoConfigEntry) -> bool:
    """Unload a remote."""
    return await hass.config_entries.async_unload_platforms(entry, platforms_for(entry.runtime_data))
