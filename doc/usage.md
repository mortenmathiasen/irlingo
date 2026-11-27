# Usage

This guide is about the `irlingo` command on a Raspberry Pi. In Home Assistant
see [irlingo in Home Assistant](home-assistant.md), on an ESP32
[irlingo on ESPHome](esphome.md).

- [Command line](#command-line)
- [Choosing a remote](#choosing-a-remote)
- [Features: keys and settings](#features-keys-and-settings)
- [Sending a key of a TV or other device](#sending-a-key-of-a-tv-or-other-device)
- [Setting an air conditioner](#setting-an-air-conditioner)
- [Remotes with a toggle bit](#remotes-with-a-toggle-bit)
- [Output and logging](#output-and-logging)
- [Exit status](#exit-status)

## Command line

```
irlingo --remote REMOTE [--feature NAME=VALUE]... [--verbose LEVEL]
irlingo --remote REMOTE --help
irlingo --list
irlingo --help
```

| Option | Meaning |
|--------|---------|
| `--remote`, `-r REMOTE` | the remote to use, see [Choosing a remote](#choosing-a-remote) |
| `--feature`, `-f NAME=VALUE` | a key or setting to send; give it once per feature |
| `--verbose`, `-v LEVEL` | how much to log: `TRACE`, `DEBUG`, `INFO`, `WARN`, `ERROR`, `FATAL` (the default) or `NOTHING` |
| `--list`, `-l` | list every remote irlingo can find |
| `--help`, `-h` | without `--remote`: usage and the number of remotes; after `--remote`: the features of that remote |

`--remote` must come before the `--feature` options. Each run sends one code; run irlingo again for the next key.

## Choosing a remote

Remotes are JSON files in a `conf/remotes/` directory, one subdirectory per manufacturer. irlingo looks in two places, in this order:

1. `conf/remotes/` below the current directory, for remotes of your own or a checkout of the source
2. the installation directory: `/usr/local/share/irlingo/conf/remotes/`, or `/usr/share/irlingo/conf/remotes/` for the release packages

`REMOTE` can be:

| Form | Example | |
|------|---------|--|
| manufacturer and model | `sony/RM-ED011` | as `irlingo --list` prints it |
| file name only | `RM-ED011`, `hvac_panasonic` | when it is unique among all remotes; otherwise irlingo lists the matching remotes |
| path to a file | `./my-aircon.json`, `/home/pi/remotes/tv.json` | any JSON file, also outside the remote directories |

Find a remote:
```
irlingo --list | grep -i samsung
irlingo --list | wc -l
```

The release packages contain all remotes. If your remote is not there, convert a LIRC file or record it, see [Managing remotes](remotes.md).

## Features: keys and settings

What a remote can send is described by its *features*. Each feature has a name and a list of values. Show them with `--help` after the remote:
```
$ irlingo --remote sony/RM-ED011 --help
Features in config file /usr/share/irlingo/conf/remotes/sony/RM-ED011.json:
       key:
              KEY_POWER
              KEY_MUTE
              KEY_VOLUMEUP
              ...
```

Names and values are case sensitive and must be written exactly as listed.

## Sending a key of a TV or other device

Remotes converted from LIRC have a single feature, `key`, with a value for each button:
```
sudo irlingo --remote sony/RM-ED011 --feature key=KEY_POWER
sudo irlingo --remote sony/RM-ED011 --feature key=KEY_VOLUMEUP
```

The code includes the repeats the original remote sends with a short press, so one run is one button press. To press a button several times, run irlingo several times, e.g. five steps of volume:
```
for i in 1 2 3 4 5; do sudo irlingo -r sony/RM-ED011 -f key=KEY_VOLUMEUP; sleep 0.3; done
```

## Setting an air conditioner

An air conditioner remote sends all its settings in every code, so the features are its settings, and one command sets everything at once:
```
$ irlingo --remote hvac_panasonic --help
Features in config file /usr/share/irlingo/conf/remotes/panasonic/hvac_panasonic.json:
       temperature:
              8
              10
              16
              ...
              30
       mode:
              AUTO
              HEAT
              COOL
              FAN
              OFF
       option:
              AUTO
              QUIET
              POWERFUL
       fan:
              AUTO
              VERYSLOW
              ...
       updown:
              ...
       leftright:
              ...

$ sudo irlingo --remote hvac_panasonic --feature mode=HEAT --feature temperature=21 \
      --feature option=AUTO --feature fan=AUTO --feature updown=HIGH --feature leftright=MIDDLE
```

A feature you leave out keeps the value in the remote's template, which is the remote's default setting, not the device's current one: the device does not tell irlingo its state. Give every feature you care about in every command.

Features are applied in the order they appear in the remote file, not the order on the command line, so where two features set the same bits the one later in the file wins. Remotes use this to copy the real remote's behaviour, e.g. for `hvac_panasonic` `mode=FAN` always sends 27 degrees and `option=QUIET` sets the fan speed. Some remotes also have *overrides* that apply only to combinations, e.g. a fan mode that is forced only while the power is on. Giving the same feature twice uses the last value.

irlingo has 47 air conditioner and heat pump remotes, named `hvac_*`. The release packages contain all of them.

Since irlingo 3.3.0: the 44 remotes for arduino-heatpumpir's models besides `hvac_nibe` and `hvac_carrier_nqv`. With an older version, copy the JSON file from [conf/remotes](../conf/remotes) and give its path to `--remote`.

`panasonic/hvac_panasonic` was reverse engineered from a Panasonic remote (e.g. JKE models), with the features temperature, mode, option, fan, updown and leftright.

The other 46 send what the [arduino-heatpumpir](https://github.com/ToniA/arduino-heatpumpir) library sends for its models, see [Managing remotes](remotes.md#air-conditioners-supported-by-arduino-heatpumpir). They all have the same features: `power` (ON, OFF), `mode` (AUTO, HEAT, COOL, DRY, FAN), `fan` (AUTO and speeds), `temperature`, `vertical` and `horizontal` (vane positions); the values depend on the model, see `--help`. They match the library's codes, but most have not been tried on the air conditioner itself; please report what works.

| Remote | Devices |
|--------|---------|
| `aux/hvac_aux` | AUX air conditioners, also Hyundai H-AR21-07H / H-AR16-09H (remote YKR-P/002E) |
| `ballu/hvac_ballu` | Ballu air conditioners |
| `carrier/hvac_carrier_mca` | Carrier MCA air conditioners |
| `carrier/hvac_carrier_nqv` | Carrier NQV, 42NQV035G / 38NYV035H2 (remote WH-L05SE) |
| `daikin/hvac_daikin` | Daikin RXS25G2V1B / FVXS25FV1B (remote ARC452A1) |
| `daikin/hvac_daikin_arc417` | Daikin air conditioners with remote ARC417 |
| `daikin/hvac_daikin_arc480` | Daikin air conditioners with remote ARC480A14 |
| `electrolux/hvac_electrolux_yal` | Electrolux air conditioners with remote YAL |
| `fuego/hvac_fuego` | Fuego air conditioners |
| `fujitsu/hvac_fujitsu_awyz` | Fujitsu Nocria AWYZ14 (remote AR-PZ2), also remotes RY3-AR and AR-RCE1E |
| `gree/hvac_gree` | Gree air conditioners |
| `gree/hvac_gree_yaa` | Gree YAA, e.g. Tosot T18H-SN/I and Tadiran (remote YAA1FB) |
| `gree/hvac_gree_yac` | Gree air conditioners with remote YAC |
| `gree/hvac_gree_yan` | Gree YAN, e.g. Vaillant VAI8 (remote YAN1F1) |
| `gree/hvac_gree_yt` | Gree air conditioners with remote YT |
| `hisense/hvac_hisense_aud` | Hisense AUD (remotes Y-H1-01, Y-H1-02(E), Y-J1, Y-E4-07) |
| `hitachi/hvac_hitachi` | Hitachi air conditioners |
| `hyundai/hvac_hyundai` | Hyundai air conditioners (remote Y512F2), probably a generic Gree model |
| `ivt/hvac_ivt` | IVT AY-XP12FR-N (remote CRMC-A673JBEZ) |
| `midea/hvac_midea` | Midea MSR1-12HRN1-QC2 (remote RG51M1/E), also Ultimate and Onnline models |
| `mitsubishi/hvac_mitsubishi_fa` | Mitsubishi Electric FA series |
| `mitsubishi/hvac_mitsubishi_fd` | Mitsubishi Electric MSZ FD-25 / FD-35 and FH series (remote KM09D 0052376) |
| `mitsubishi/hvac_mitsubishi_fe` | Mitsubishi Electric FE series |
| `mitsubishi/hvac_mitsubishi_kj` | Mitsubishi Electric KJ series |
| `mitsubishi/hvac_mitsubishi_msc` | Mitsubishi Electric MSC-GA20VB / GA25VB / GA35VB (remote KP1A) |
| `mitsubishi/hvac_mitsubishi_msy` | Mitsubishi Electric MSY series |
| `mitsubishi/hvac_mitsubishi_sez` | Mitsubishi Electric SEZ-KDxx ducted units |
| `mitsubishi_heavy/hvac_mitsubishi_heavy_fdtc` | Mitsubishi Heavy FDTCxxVF (remote PJA502A704AA) |
| `mitsubishi_heavy/hvac_mitsubishi_heavy_zj` | Mitsubishi Heavy SRKxxZJ-S (remote RKX502A001C) |
| `mitsubishi_heavy/hvac_mitsubishi_heavy_zm` | Mitsubishi Heavy SRKxxZM-S (remote RLA502A700B) and SRKxxZMP-S (remote RKX502A001P) |
| `nibe/hvac_nibe` | Nibe air to air heat pumps (AG-WL10-4, probably AG-WT10) |
| `olimpia/hvac_olimpia` | Olimpia Splendid Maestro |
| `panasonic/hvac_panasonic_ckp` | Panasonic E9/E12-CKP (remote A75C2295) |
| `panasonic/hvac_panasonic_dke` | Panasonic E9/E12-DKE (remote A75C2616) |
| `panasonic/hvac_panasonic_eke` | Panasonic EKE air conditioners |
| `panasonic/hvac_panasonic_jke` | Panasonic E9/E12-JKE (see also `panasonic/hvac_panasonic`) |
| `panasonic/hvac_panasonic_lke` | Panasonic LKE air conditioners |
| `panasonic/hvac_panasonic_nke` | Panasonic E9/E12-NKE |
| `philco/hvac_philco_phs32` | Philco PHS32 |
| `samsung/hvac_samsung_aqv` | Samsung AQV12PSBN / AQV09ASA / AQV12MSAN (remote ARH-1362) |
| `samsung/hvac_samsung_fjm` | Samsung FJM, RJ040F2HXEA / 2XMH026FNEA (remote ARH-465) |
| `sharp/hvac_sharp` | Sharp AY-ZP40KR (remote CRMC-A788JBEZ) |
| `toshiba/hvac_toshiba` | Toshiba air conditioners |
| `toshiba/hvac_toshiba_daiseikai` | Toshiba Daiseikai, e.g. RAS-10G2KVP-E / RAS-13G2KVP-E (remote WH-TA01EE) |
| `zh/hvac_zhjg01` | Air conditioners with the generic remote ZH/JG-01 |
| `zh/hvac_zhlt01` | Air conditioners with the generic remote ZH/LT-01: Eurom, Chigo, Tristar, Tecnomaster, Elgin, Tekno, Proma, Sumikura, Nakatomy and others |

## Remotes with a toggle bit

Some protocols, e.g. Philips RC5 and RC6, flip a bit on every new press of any key, so the device can tell two presses of `5` (`55`) from one long press. irlingo does this automatically for remotes with a `toggle` section: it remembers the state of each remote in a file and flips it after every successful transmission.

| Running as | State file |
|------------|------------|
| any user, with `IRLINGO_STATE_DIR` set | `$IRLINGO_STATE_DIR/toggle-state` |
| root (e.g. with `sudo`) | `/var/lib/irlingo/toggle-state` |
| other users | `$XDG_STATE_HOME/irlingo/toggle-state`, by default `~/.local/state/irlingo/toggle-state` |

If irlingo runs both with and without `sudo`, set `IRLINGO_STATE_DIR` so both use the same file. Deleting the file starts all remotes from the first press again. If the file cannot be written, irlingo logs a warning and still transmits.

## Output and logging

By default irlingo prints nothing when it succeeds, and only fatal errors otherwise. Log messages go to standard error, with the time, level and source line. (The `pigpio` backend also prints a `gpioWaveTxSend OK` line.) `--verbose` shows more:

| Level | Shows |
|-------|-------|
| `INFO` | the remote file, its description and the code sent |
| `DEBUG` | also the toggle state, the transmitter device and the symbols transmitted |
| `TRACE` | also checksum calculations and pulse counts |

```
sudo irlingo -r hvac_panasonic -f mode=HEAT -f temperature=21 --verbose=DEBUG
```

The code is shown as a string of symbols, one character per mark and space pair of the remote's `symboldefinitions`, e.g. `H-01000000-...`. See [Remote file format](remote-format.md).

## Exit status

| Status | Meaning |
|--------|---------|
| 0 | the code was transmitted, or `--list` printed the remotes |
| 1 | an error: unknown remote or feature, invalid remote file, transmitter not available or not writable. `--help` also exits with 1, with or without `--remote`. |

Scripts can check it, e.g. `sudo irlingo -r tv -f key=KEY_POWER || echo "sending failed"`. Log messages, including errors from the transmitter, go to standard error; messages about the command line (unknown remote or feature, usage) go to standard output. The causes of errors are described in [Troubleshooting](troubleshooting.md).
