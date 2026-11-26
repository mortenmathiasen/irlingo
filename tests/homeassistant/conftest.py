"""Fixtures for the irlingo integration's tests: a fake infrared emitter."""

from pathlib import Path
import sys

from homeassistant.components.infrared import InfraredCommand, InfraredEmitterEntity
from homeassistant.components.infrared.const import DATA_COMPONENT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import pytest

# custom_components/ of this repository
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load the integration from custom_components/."""
    return


class FakeEmitter(InfraredEmitterEntity):
    """An infrared emitter recording the commands it is asked to send."""

    _attr_name = "Fake emitter"
    _attr_unique_id = "fake_emitter"

    def __init__(self) -> None:
        """No commands sent yet."""
        self.commands: list[InfraredCommand] = []

    async def async_send_command(self, command: InfraredCommand) -> None:
        """Record the command."""
        self.commands.append(command)


@pytest.fixture
async def emitter(hass: HomeAssistant) -> FakeEmitter:
    """An infrared emitter, infrared.fake_emitter."""
    assert await async_setup_component(hass, "infrared", {})
    entity = FakeEmitter()
    await hass.data[DATA_COMPONENT].async_add_entities([entity])
    await hass.async_block_till_done()
    assert entity.entity_id == "infrared.fake_emitter"
    return entity
