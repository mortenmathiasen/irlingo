"""The irlingo integration: config flow and entities, with a fake emitter."""

from homeassistant.components.climate import HVACMode
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant, State
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, mock_restore_cache

from custom_components.irlingo.const import CONF_INFRARED_EMITTER_ENTITY_ID, CONF_REMOTE, DOMAIN
from custom_components.irlingo.remotes import load_remote

EMITTER = "infrared.fake_emitter"


async def add_remote(hass: HomeAssistant, remote: str, title: str) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=title,
        data={CONF_REMOTE: remote, CONF_INFRARED_EMITTER_ENTITY_ID: EMITTER},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def expected_timings(remote: str, features: dict[str, str], toggled: bool = False) -> list[int]:
    loaded = load_remote(remote)
    return loaded.timings(loaded.encode(features, toggled))


async def test_flow_without_emitters(hass: HomeAssistant) -> None:
    """Without an infrared emitter there is nothing to send through."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_infrared_emitters"


async def test_flow(hass: HomeAssistant, emitter) -> None:
    """Manufacturer, then remote, emitter and name."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"manufacturer": "sony"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "remote"

    with pytest.raises(InvalidData):  # not one of the manufacturer's remotes
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_REMOTE: "sony/not-a-remote", CONF_INFRARED_EMITTER_ENTITY_ID: EMITTER},
        )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_REMOTE: "sony/RM-ED011", CONF_INFRARED_EMITTER_ENTITY_ID: EMITTER, "name": "Living room TV"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room TV"
    assert result["data"] == {CONF_REMOTE: "sony/RM-ED011", CONF_INFRARED_EMITTER_ENTITY_ID: EMITTER}


async def test_tv_buttons_and_remote(hass: HomeAssistant, emitter) -> None:
    """A TV remote: a button per key, and remote.send_command."""
    entry = await add_remote(hass, "sony/RM-ED011", "TV")
    registry = er.async_get(hass)
    buttons = [e for e in er.async_entries_for_config_entry(registry, entry.entry_id) if e.domain == "button"]
    assert len(buttons) == 32
    power = registry.async_get_entity_id("button", DOMAIN, f"{entry.entry_id}_key_KEY_POWER")
    assert power is not None

    await hass.services.async_call("button", "press", {"entity_id": power}, blocking=True)
    assert len(emitter.commands) == 1
    assert emitter.commands[0].modulation == 40000
    assert emitter.commands[0].get_raw_timings() == expected_timings("sony/RM-ED011", {"key": "KEY_POWER"})

    await hass.services.async_call(
        "remote",
        "send_command",
        {"entity_id": "remote.tv_remote", "command": ["KEY_POWER", "key=KEY_AUDIO"], "delay_secs": 0},
        blocking=True,
    )
    assert len(emitter.commands) == 3
    assert emitter.commands[2].get_raw_timings() == expected_timings("sony/RM-ED011", {"key": "KEY_AUDIO"})

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "remote", "send_command", {"entity_id": "remote.tv_remote", "command": "KEY_NOPE"}, blocking=True
        )

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_air_conditioner(hass: HomeAssistant, emitter) -> None:
    """An air conditioner remote with power, mode, temperature and fan features."""
    await add_remote(hass, "daikin/hvac_daikin", "Bedroom AC")
    state = hass.states.get("climate.bedroom_ac")
    assert state is not None
    assert state.state == HVACMode.OFF
    assert set(state.attributes["hvac_modes"]) == {"off", "cool", "heat_cool", "heat", "dry", "fan_only"}
    assert state.attributes["min_temp"] == 18
    assert state.attributes["fan_modes"][0] == "auto"
    assert not emitter.commands  # nothing is sent at start-up

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.bedroom_ac", "temperature": 23.4, "hvac_mode": "heat"},
        blocking=True,
    )
    assert emitter.commands[-1].get_raw_timings() == expected_timings(
        "daikin/hvac_daikin", {"mode": "HEAT", "power": "ON", "temperature": "23", "fan": "AUTO"}
    )
    state = hass.states.get("climate.bedroom_ac")
    assert state.state == HVACMode.HEAT
    assert state.attributes["temperature"] == 23

    await hass.services.async_call(
        "climate", "set_fan_mode", {"entity_id": "climate.bedroom_ac", "fan_mode": "3"}, blocking=True
    )
    assert emitter.commands[-1].get_raw_timings() == expected_timings(
        "daikin/hvac_daikin", {"mode": "HEAT", "power": "ON", "temperature": "23", "fan": "3"}
    )

    await hass.services.async_call("climate", "turn_off", {"entity_id": "climate.bedroom_ac"}, blocking=True)
    assert emitter.commands[-1].get_raw_timings() == expected_timings(
        "daikin/hvac_daikin", {"power": "OFF", "temperature": "23", "fan": "3"}
    )
    await hass.services.async_call("climate", "turn_on", {"entity_id": "climate.bedroom_ac"}, blocking=True)
    assert hass.states.get("climate.bedroom_ac").state == HVACMode.HEAT
    assert len(emitter.commands) == 4


async def test_toggle_bit(hass: HomeAssistant, emitter) -> None:
    """A remote with a toggle bit sends the other code every other press."""
    remote = "accessmedia/ThinBox"
    loaded = load_remote(remote)
    assert loaded.has_toggle
    key = next(iter(loaded.data["toggle"]["key"]))
    entry = await add_remote(hass, remote, "Box")
    button = er.async_get(hass).async_get_entity_id("button", DOMAIN, f"{entry.entry_id}_key_{key}")
    for _ in range(3):
        await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)
    sent = [command.get_raw_timings() for command in emitter.commands]
    assert sent[0] == expected_timings(remote, {"key": key}, False)
    assert sent[1] == expected_timings(remote, {"key": key}, True)
    assert sent[2] == sent[0]
    assert sent[0] != sent[1]


async def test_unknown_remote(hass: HomeAssistant, emitter) -> None:
    """A config entry whose remote no longer exists fails to set up."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="Gone", data={CONF_REMOTE: "sony/gone", CONF_INFRARED_EMITTER_ENTITY_ID: EMITTER}
    )
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)


async def test_climate_restores_without_sending(hass: HomeAssistant, emitter) -> None:
    """After a restart the last state comes back, and nothing is sent."""
    mock_restore_cache(
        hass,
        [State("climate.bedroom_ac", HVACMode.COOL, {"temperature": 19.6, "fan_mode": "2"})],
    )
    await add_remote(hass, "daikin/hvac_daikin", "Bedroom AC")
    state = hass.states.get("climate.bedroom_ac")
    assert state.state == HVACMode.COOL
    assert state.attributes["temperature"] == 20
    assert state.attributes["fan_mode"] == "2"
    assert not emitter.commands
