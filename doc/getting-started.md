# Getting started

irlingo sends infrared codes like a remote control does: to TVs, receivers,
air conditioners, heat pumps and anything else with an IR receiver. It comes
with more than 3000 remotes, 47 of them for air conditioners and heat pumps,
and builds the code for any key or setting of a remote, e.g. *heat, 21 °C, fan
auto*.

The same remotes and the same encoder run in three places:

| | What it is | Runs on |
|-|------------|---------|
| **The `irlingo` command** | a command line tool, for scripts, cron, Node-RED and other software | a Raspberry Pi with an IR LED |
| **The ESPHome component** | the remotes built into an ESP32's firmware, as climate entities, buttons and automations | an ESP32 (or ESP8266, RP2040) with an IR LED |
| **The Home Assistant integration** | the remotes in Home Assistant, sent through an infrared emitter | Home Assistant, with an ESP32, Broadlink or other emitter |

All of them send the same code for the same remote and setting. Choose in two
steps: the hardware that sends, then what controls it.

- [Step 1: the hardware](#step-1-the-hardware)
- [Step 2: what controls it](#step-2-what-controls-it)
- [Step 3: install](#step-3-install)

## Step 1: the hardware

Something with an IR LED has to be within sight of the device, usually in the
same room.

| Choose | When |
|--------|------|
| **An ESP32** | the usual choice: a board for a few euros with an IR LED, on Wi-Fi, placed anywhere with a USB supply; with or without Home Assistant |
| **An infrared emitter you already have** | Home Assistant already has one, e.g. a Broadlink remote: only the integration is needed, no soldering |
| **A Raspberry Pi** | you want the `irlingo` command: scripts, cron, Node-RED, or a Pi that is already near the device, e.g. with the [ANAVI Infrared pHAT](https://anavi.technology/) |

An ESP32 and a Raspberry Pi both need an IR LED circuit, see
[Connecting an IR LED](hardware.md): an IR LED, a transistor and three
resistors, or a ready-made board.

## Step 2: what controls it

| Choose | Hardware | When |
|--------|----------|------|
| **Home Assistant with the integration** | an ESP32, or any emitter Home Assistant has | the quickest setup with Home Assistant: remotes are added from the user interface, all of them available, no firmware install per remote |
| **Home Assistant with the ESPHome component** | an ESP32 | the ESP32 must also work on its own, e.g. timers on the device, or when Home Assistant or the network is down |
| **The ESP32 on its own** | an ESP32 | no Home Assistant: a web page on the ESP32, schedules, push buttons, or MQTT |
| **The `irlingo` command** | a Raspberry Pi | scripts, cron, Node-RED, other home automation software, or Home Assistant through `shell_command` |

The integration and the ESPHome component can share one ESP32; see
[The ESPHome component or the integration?](home-assistant.md#the-esphome-component-or-the-integration)
for a detailed comparison.

## Step 3: install

**Home Assistant with the integration**

1. An ESP32 with an IR LED, see [Connecting an IR LED](hardware.md#esp32-and-other-esphome-chips),
   set up as an emitter, see [Setting up an infrared emitter](home-assistant.md#setting-up-an-infrared-emitter);
   or an emitter you already have.
2. Install the integration and add your remotes, see
   [Installing](home-assistant.md#installing) and
   [Adding a remote](home-assistant.md#adding-a-remote).

**The ESPHome component, with or without Home Assistant**

1. An ESP32 with an IR LED, see [Connecting an IR LED](hardware.md#esp32-and-other-esphome-chips).
2. Add irlingo and your remotes to its YAML, see
   [irlingo on ESPHome](esphome.md#configuration).
3. With Home Assistant, the device's climate entities and buttons show up
   there through ESPHome; without it, see
   [Without Home Assistant](esphome.md#without-home-assistant).

**The `irlingo` command on a Raspberry Pi**

1. An IR LED on the Pi, see [Connecting an IR LED](hardware.md#raspberry-pi).
2. Install the package and enable the transmitter, see
   [Installation](installation.md).
3. Find your remote and send, see [Usage](usage.md); for scripts, cron, Home
   Assistant and Node-RED see [Integration](integration.md).

**The device is in another place**, e.g. a summer house, and Home Assistant at
home: an ESP32 there connects home through WireGuard, see
[An ESP32 in another place](remote-location.md).

**Your remote is not included:** convert a LIRC file or record your remote,
see [Managing remotes](remotes.md).
