"""Constants for the irlingo integration."""

from typing import Final

DOMAIN: Final = "irlingo"

CONF_REMOTE: Final = "remote"
CONF_MANUFACTURER: Final = "manufacturer"
CONF_INFRARED_EMITTER_ENTITY_ID: Final = "infrared_emitter_entity_id"

# Carrier frequency for remotes that give none, as LIRC assumes
DEFAULT_FREQUENCY: Final = 38000

# Home Assistant HVAC modes for a remote's mode values (as the ESPHome component guesses them)
MODE_GUESSES: Final = {
    "AUTO": "heat_cool",
    "HEAT": "heat",
    "COOL": "cool",
    "DRY": "dry",
    "FAN": "fan_only",
    "FAN_ONLY": "fan_only",
    "OFF": "off",
}
