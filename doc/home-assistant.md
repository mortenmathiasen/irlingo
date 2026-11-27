# irlingo in Home Assistant

The irlingo integration sends irlingo's remotes from Home Assistant, through
any infrared emitter Home Assistant has: an ESP32 with an IR LED running
ESPHome, a Broadlink remote, an SMLIGHT device and others. Air conditioners
become climate entities; TVs, receivers and other remotes get a button for
each key and a remote entity for automations.

It encodes the codes itself, with a Python port of irlingo's encoder that the
test suite checks against the C encoder for every feature value of every
remote, so Home Assistant sends what the `irlingo` command and the ESPHome
component send.

- [Requirements](#requirements)
- [Setting up an infrared emitter](#setting-up-an-infrared-emitter)
- [Installing](#installing)
- [Adding a remote](#adding-a-remote)
- [Entities](#entities)
- [Sending from automations](#sending-from-automations)
- [Air conditioners](#air-conditioners)
- [Limitations](#limitations)
- [The ESPHome component or the integration?](#the-esphome-component-or-the-integration)
- [An emitter in another place](#an-emitter-in-another-place)

## Requirements

- Home Assistant 2026.10 or newer. The integration uses Home Assistant's
  infrared entities, which are new; it is tested with 2026.10.
- An infrared emitter entity (`infrared.*`) from another integration, e.g. an
  ESPHome device with an IR transmitter, or a Broadlink remote. Without one,
  adding a remote stops with "No infrared emitter found"; see
  [Setting up an infrared emitter](#setting-up-an-infrared-emitter).

## Setting up an infrared emitter

The integration builds the codes; an infrared emitter entity sends them.

### An ESP32 with ESPHome

1. Connect an IR LED to the ESP32, see
   [Connecting an IR LED](hardware.md#esp32-and-other-esphome-chips).
2. Add the transmitter and ESPHome's `infrared` emitter to the device's YAML,
   e.g. in ESPHome Builder:

   ```yaml
   remote_transmitter:
     id: ir_tx
     pin: GPIO4
     carrier_duty_percent: 50%
     non_blocking: true

   infrared:
     - platform: ir_rf_proxy
       name: IR emitter
       remote_transmitter_id: ir_tx
   ```

   The device also needs the usual `api:` for Home Assistant. Tested with
   ESPHome 2026.11.
3. Install the firmware. Home Assistant then has an entity
   `infrared.<device>_ir_emitter`, e.g. `infrared.ir_livingroom_ir_emitter`,
   under the device in Settings → Devices & services → ESPHome.
4. Check that it sends: add a remote (see [Adding a remote](#adding-a-remote)),
   press one of its buttons and look at the LED through a phone camera, which
   shows infrared as a flashing light; see also
   [Testing with a visible LED](hardware.md#testing-with-a-visible-led).

The ESP32 needs no remotes in its firmware for this. The `infrared` emitter can
also sit next to the [irlingo ESPHome component](esphome.md) on the same
`remote_transmitter`: the ESP32 then sends its own remotes and the
integration's, see
[The ESPHome component or the integration?](#the-esphome-component-or-the-integration).

### Other emitters

Other integrations with infrared emitter entities work the same way, e.g.
[Broadlink](https://www.home-assistant.io/integrations/broadlink/) remotes.
Set them up as their integration describes; the emitter then shows up when
adding a remote.

## Installing

With [HACS](https://hacs.xyz/):

1. HACS → ⋮ → Custom repositories: add `https://github.com/mortenmathiasen/irlingo`
   with the type *Integration*.
2. Search for *irlingo* in HACS and download it.
3. Restart Home Assistant.

Without HACS, download `irlingo-homeassistant.zip` from the
[latest release](https://github.com/mortenmathiasen/irlingo/releases/latest),
extract it into `config/custom_components/irlingo/` and restart Home Assistant.

The integration carries every irlingo remote (about 2.7 MB), so it needs no
internet access afterwards.

## Adding a remote

Settings → Devices & services → Add integration → *irlingo*:

1. Choose the manufacturer of your device.
2. Choose the remote, the infrared emitter that sends it, and optionally a
   name. Air conditioner remotes are named `hvac_*`, e.g. `daikin/hvac_daikin`
   (see [Setting an air conditioner](usage.md#setting-an-air-conditioner) for
   which model to choose).

Add the integration again for each device. Several devices can share one
emitter.

Your own remotes (from [lirc2irlingo or ir2irlingo](remotes.md)) can be added by
copying them into `config/custom_components/irlingo/remotes/<manufacturer>/`;
they then show up in the list. An update of the integration replaces that
directory, so keep a copy.

## Entities

Each remote becomes a device with:

| Entity | For | |
|--------|-----|-|
| `climate` | air conditioner remotes | the mode, target temperature and fan speed, see [Air conditioners](#air-conditioners) |
| `button` | remotes with keys | one per key, e.g. *KEY_POWER*, named as in the remote file |
| `remote` | every remote | `remote.send_command`, see below |

The entities are unavailable while the emitter is. Remotes with a toggle bit
send the other code every other press, as the real remote does; which one is
next is kept across restarts.

## Sending from automations

`remote.send_command` sends keys by name, or any feature values of the remote
as `NAME=VALUE` pairs:

```yaml
action: remote.send_command
target:
  entity_id: remote.living_room_tv_remote
data:
  command:
    - KEY_POWER
    - KEY_VOLUMEUP
  num_repeats: 1
  delay_secs: 0.4
```

```yaml
action: remote.send_command
target:
  entity_id: remote.bedroom_ac_remote
data:
  command: "power=ON mode=HEAT temperature=21 fan=AUTO"
```

The feature names and values of a remote are listed by `irlingo --remote NAME
--help`, or in its file in
[conf/remotes](https://github.com/mortenmathiasen/irlingo/tree/master/conf/remotes).

## Air conditioners

Remotes with a `mode` feature become climate entities. The modes are guessed
from the remote's values (HEAT, COOL, DRY, FAN, AUTO and OFF), and a `power`
feature with ON and OFF gives the *off* mode. `temperature` gives the target
temperature, rounded to the nearest value the remote has, and `fan` the fan
speeds: AUTO becomes *auto*, the other values are offered by name.

Every change sends one code with the mode, the temperature and the fan speed,
as the real remote does. The state is assumed: it is the last one sent, since
an air conditioner does not report back. After a restart the last state comes
back without anything being sent, so a restart does not switch the air
conditioner.

On a dashboard, a thermostat card with the mode and fan speed as drop-down
lists:

```yaml
type: thermostat
entity: climate.bedroom_ac
features:
  - type: climate-hvac-modes
    style: dropdown
  - type: climate-fan-modes
    style: dropdown
```

## Limitations

- Sending only: the integration does not learn codes. To add a remote, convert
  or record it with irlingo's tools, see [Managing remotes](remotes.md).
- The infrared emitter must send the code's carrier frequency, as most do.
  The duty cycle is the emitter's own.
- Codes needing more than 1024 pulses and spaces, e.g. some remotes made with
  `ir2irlingo --fallback`, cannot be sent, as with the irlingo command.

## The ESPHome component or the integration?

Both send the same codes, built by the same encoder. They differ in where the
remotes live:

| | [ESPHome component](esphome.md) | Integration |
|-|------------------|-------------|
| Remotes | built into the ESP32's firmware | in Home Assistant |
| Emitter | an ESP32, ESP8266 or RP2040 running ESPHome | any infrared emitter entity: ESPHome, Broadlink and others |
| Set up in | YAML, then a firmware install per change | the user interface; a new remote needs no firmware install |
| Without Home Assistant | works: schedules, buttons, a web page, see [Without Home Assistant](esphome.md#without-home-assistant) | does not work |
| Without a network | schedules and buttons on the ESP32 still send | does not work |
| Air conditioners | `climate` entities, mapped without configuration for 47 air conditioner remotes | `climate` entities for remotes with a `mode` feature |
| Other remotes | a `button` per key you configure, `irlingo.send` in automations | a `button` per key, `remote.send_command` |
| Remotes on the device | limited by its flash, see [Memory and limits](esphome.md#memory-and-limits) | every irlingo remote, and your own |

Choose:

- **The integration** when Home Assistant is always there: setup is quickest,
  every remote is available without a firmware install, and it works with
  emitters you already have.
- **The ESPHome component** when the device must work on its own: without Home
  Assistant, without a network connection, or with timers on the device.
- **Both** on one ESP32, as in
  [An ESP32 with ESPHome](#an-esp32-with-esphome): the remotes that must work
  on their own in the firmware, the rest from the integration.

## An emitter in another place

The emitter does not have to be on Home Assistant's network: an ESP32 in a
summer house can connect home through a WireGuard tunnel, see
[An ESP32 in another place](remote-location.md).
