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
- [Installing](#installing)
- [Adding a remote](#adding-a-remote)
- [Entities](#entities)
- [Sending from automations](#sending-from-automations)
- [Air conditioners](#air-conditioners)
- [Limitations](#limitations)
- [The ESPHome component or the integration?](#the-esphome-component-or-the-integration)

## Requirements

- Home Assistant 2026.10 or newer. The integration uses Home Assistant's
  infrared entities, which are new; it is tested with 2026.10.
- An infrared emitter entity (`infrared.*`) from another integration, e.g. an
  ESPHome device with an IR transmitter, or a Broadlink remote. Without one,
  adding a remote stops with "No infrared emitter found".

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

## Limitations

- Sending only: the integration does not learn codes. To add a remote, convert
  or record it with irlingo's tools, see [Managing remotes](remotes.md).
- The infrared emitter must send the code's carrier frequency, as most do.
  The duty cycle is the emitter's own.
- Codes needing more than 1024 pulses and spaces, e.g. some remotes made with
  `ir2irlingo --fallback`, cannot be sent, as with the irlingo command.

## The ESPHome component or the integration?

Both send the same codes. The [ESPHome component](esphome.md) builds the
remotes into the ESP32's firmware, so it works without Home Assistant, and is
configured in YAML. The integration keeps the remotes in Home Assistant and
works with any infrared emitter, including ESPHome devices with a plain IR
transmitter, and is set up from the user interface.
