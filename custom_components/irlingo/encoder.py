"""irlingo's encoder in Python: feature values to IR timings.

A port of irlingo's portable C core (components/irlingo/: irremote.c,
checksum.c, pulses.c and the hvac_panasonic plugin), so Home Assistant sends
exactly the codes the irlingo command and the ESPHome component send. The
test suite checks it against every remote's test vectors and against the C
encoder for every feature value.

This module has no Home Assistant dependency.
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Longest code, in symbols, and most pulses and spaces in one code (pulses.h)
MAX_COMMAND_SIZE = 2048
MAX_PULSE_VALUES = 1024

_U32 = 0xFFFFFFFF


class EncodeError(Exception):
    """A code cannot be built: an invalid checksum, plugin or symbol."""


class Remote:
    """A remote: its JSON definition, and the codes it sends for feature values."""

    def __init__(self, data: Mapping[str, Any], name: str = "(remote)") -> None:
        """Use a remote's parsed JSON; name names it in messages."""
        if not isinstance(data, Mapping):
            raise EncodeError(f"Remote {name} is not a JSON object")
        self.data = data
        self.name = name

    # The remote's settings

    @property
    def features(self) -> dict[str, dict[str, str]]:
        """The features and the codes of their values, in the remote's order."""
        features = self.data.get("features")
        return features if isinstance(features, dict) else {}

    def has_feature(self, name: str, value: str) -> bool:
        """Whether the remote has this feature value."""
        values = self.features.get(name)
        return isinstance(values, dict) and value in values

    @property
    def symbols(self) -> list[tuple[str, int, int]]:
        """The symbols and their mark and space durations in microseconds."""
        definitions = self.data.get("symboldefinitions")
        if not isinstance(definitions, dict):
            return []
        return [
            (symbol[0], _whole(spec.get("mark")), _whole(spec.get("space")))
            for symbol, spec in definitions.items()
            if symbol and isinstance(spec, dict)
        ]

    @property
    def frequency(self) -> int:
        """The carrier frequency in Hz, 0 when the remote gives none."""
        return _whole(self.data.get("frequency"))

    @property
    def plugin(self) -> str | None:
        """The remote's plugin. A remote without a plugin, checksums or variants
        whose name contains hvac_panasonic gets that plugin, as in PIIR 1.x."""
        plugin = self.data.get("plugin")
        if isinstance(plugin, str):
            return plugin
        if not self.data.get("checksums") and not self.data.get("variants") and "hvac_panasonic" in self.name:
            return "hvac_panasonic"
        return None

    @property
    def has_toggle(self) -> bool:
        """Whether the remote has a toggle bit, sending other codes every other press."""
        toggle = self.data.get("toggle")
        return isinstance(toggle, dict) and len(toggle) > 0

    # Encoding

    def encode(self, requested: Mapping[str, str] | None, toggled: bool = False) -> str:
        """The code for these feature values: the template with the features,
        overrides and variants applied, then checksums and the plugin."""
        code, definition = self._featured_code(requested, toggled)
        checksums = definition.get("checksums") if isinstance(definition, dict) else None
        if checksums:
            code = apply_checksums(checksums, code)
        return apply_plugin(self.plugin, code)

    def timings(self, code: str) -> list[int]:
        """The pulses (positive) and spaces (negative) of a code, in microseconds."""
        return build_timings(self.symbols, code)

    def _featured_code(self, requested: Mapping[str, str] | None, toggled: bool) -> tuple[str, Mapping[str, Any]]:
        """irRemoteEncode(): the code before checksums, and the definition used."""
        requested = dict(requested) if requested is not None else None
        definition = self._select_definition(requested)
        template = definition.get("template")
        if not isinstance(template, str):
            _LOGGER.error("Remote %s has no template", self.name)
            template = ""
        code = list(template)
        if requested is None:
            return template, definition

        # A variant has its own features, if any: their codes refer to its template
        if definition is self.data:
            definitions = self.features
        else:
            definitions = definition.get("features")
            definitions = definitions if isinstance(definitions, dict) else {}
        toggles = self.data.get("toggle") if isinstance(self.data.get("toggle"), dict) else {}
        for name, values in definitions.items():
            value = requested.get(name)
            if value is None:
                continue
            overlay = values.get(value) if isinstance(values, dict) else None
            if not isinstance(overlay, str):
                overlay = None
            if overlay is not None and toggled and definition is self.data:
                toggle = toggles.get(name)
                toggle_code = toggle.get(value) if isinstance(toggle, dict) else None
                if isinstance(toggle_code, str):
                    overlay = toggle_code
            if overlay is None:
                _LOGGER.error("Feature '%s'='%s' not found in %s", name, value, self.name)
                continue
            _apply_overlay(overlay, code)

        overrides = definition.get("overrides")
        for index, override in enumerate(overrides if isinstance(overrides, list) else []):
            when = override.get("when") if isinstance(override, dict) else None
            overlay = override.get("code") if isinstance(override, dict) else None
            if not isinstance(when, dict) or not isinstance(overlay, str):
                _LOGGER.error('Override %d in %s needs "when" and "code"', index, self.name)
                continue
            if _when_matches(when, requested):
                _apply_overlay(overlay, code)
        return "".join(code), definition

    def _select_definition(self, requested: dict[str, str] | None) -> Mapping[str, Any]:
        """The first of the variants whose "when" features are all requested, or
        the remote itself."""
        variants = self.data.get("variants")
        if requested is None or not isinstance(variants, list):
            return self.data
        for index, variant in enumerate(variants):
            when = variant.get("when") if isinstance(variant, dict) else None
            if not isinstance(when, dict) or not isinstance(variant.get("template"), str):
                _LOGGER.error('Variant %d in %s needs "when" and "template"', index, self.name)
                continue
            if _when_matches(when, requested):
                return variant
        return self.data


def _whole(value: Any) -> int:
    """A JSON number as a C (int) cast makes it, 0 when it is not a number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value)


def _apply_overlay(overlay: str, code: list[str]) -> None:
    """Copy the symbols of an overlay to code, except spaces."""
    if len(overlay) > len(code):
        _LOGGER.warning("Feature code '%s' is longer than the template (%d symbols)", overlay, len(code))
    for i, symbol in enumerate(overlay[: len(code)]):
        if symbol != " ":
            code[i] = symbol


def _when_matches(when: Mapping[str, Any], requested: Mapping[str, str]) -> bool:
    """All features of a "when" object are requested with its values."""
    for name, wanted in when.items():
        value = requested.get(name)
        if not isinstance(wanted, str) or value is None or wanted != value:
            return False
    return True


# Checksums (checksum.c)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _read_number(spec: Mapping[str, Any], name: str, required: bool, maximum: int) -> int | None:
    """An optional whole number from 0 to maximum; None when missing."""
    if name not in spec:
        if required:
            raise EncodeError(f'Checksum needs "{name}"')
        return None
    value = spec[name]
    if not _is_number(value) or value < 0 or value > maximum or value != int(value):
        raise EncodeError(f'Checksum "{name}" must be a whole number from 0 to {maximum}')
    return int(value)


def _read_flag(spec: Mapping[str, Any], name: str) -> bool:
    value = spec.get(name, False)
    if not isinstance(value, bool):
        raise EncodeError(f'Checksum "{name}" must be true or false')
    return value


def _read_unit_list(array: Any, name: str) -> list[int]:
    if not isinstance(array, list) or not array:
        raise EncodeError(f'Checksum "{name}" must be a list of unit numbers')
    for value in array:
        if not _is_number(value) or value < 0 or value > MAX_COMMAND_SIZE or value != int(value):
            raise EncodeError(f'Checksum "{name}" must hold whole numbers from 0 to {MAX_COMMAND_SIZE}')
    return [int(value) for value in array]


def _covered_units(spec: Mapping[str, Any]) -> list[int]:
    """The units a checksum covers, from "data" or from "from" to "to"."""
    if "data" in spec and ("from" in spec or "to" in spec):
        raise EncodeError('Checksum needs either "data" or "from" and "to", not both')
    if "data" in spec:
        return _read_unit_list(spec["data"], "data")
    start = _read_number(spec, "from", True, MAX_COMMAND_SIZE)
    end = _read_number(spec, "to", True, MAX_COMMAND_SIZE)
    if start > end:
        raise EncodeError(f'Checksum "from" ({start}) is after "to" ({end})')
    return list(range(start, end + 1))


def _result_units(spec: Mapping[str, Any]) -> list[int]:
    """The units the result is written into, "at": a unit number or a list."""
    if isinstance(spec.get("at"), list):
        return _read_unit_list(spec["at"], "at")
    return [_read_number(spec, "at", True, MAX_COMMAND_SIZE)]


def _optional_string(spec: Mapping[str, Any], name: str, message: str) -> str | None:
    """A string setting, None when missing; anything else than a string is invalid."""
    if name not in spec:
        return None
    if not isinstance(spec[name], str):
        raise EncodeError(message)
    return spec[name]


def _reflect(value: int, width: int) -> int:
    result = 0
    for i in range(width):
        if value & (1 << i):
            result |= 1 << (width - 1 - i)
    return result


def _crc_unit(crc: int, unit: int, unit_width: int, poly: int, crc_width: int, reflected: bool, mask: int) -> int:
    """Feed a unit of unit_width bits to a CRC register of crc_width bits."""
    for i in range(unit_width):
        if reflected:
            bit = (crc ^ (unit >> i)) & 1
            crc >>= 1
            if bit:
                crc ^= _reflect(poly, crc_width)
        else:
            bit = ((crc >> (crc_width - 1)) ^ (unit >> (unit_width - 1 - i))) & 1
            crc = (crc << 1) & mask
            if bit:
                crc ^= poly
    return crc & _U32


def _apply_checksum(spec: Mapping[str, Any], code: list[str]) -> None:
    kind = spec.get("type")
    if kind not in ("sum", "xor", "popcount", "crc"):
        raise EncodeError('Checksum "type" must be "sum", "xor", "popcount" or "crc"')

    message = 'Checksum "unit" must be "byte" or "nibble"'
    unit = _optional_string(spec, "unit", message)
    if unit is not None and unit not in ("byte", "nibble"):
        raise EncodeError(message)
    width = 4 if unit == "nibble" else 8
    unit_name = "nibble" if width == 4 else "byte"

    at = _result_units(spec)
    result_width = width * len(at)
    if result_width > 32:
        raise EncodeError(f"Checksum result of {result_width} bits is wider than 32 bits")
    mask = _U32 if result_width >= 32 else (1 << result_width) - 1

    init = _read_number(spec, "init", False, mask) or 0
    xorout = _read_number(spec, "xorout", False, mask) or 0
    poly = _read_number(spec, "poly", kind == "crc", mask) or 0
    invert = _read_flag(spec, "invert")
    negate = _read_flag(spec, "negate")
    reflected = _read_flag(spec, "reflect")
    if kind != "crc" and ("poly" in spec or "reflect" in spec):
        raise EncodeError('Checksum "poly" and "reflect" are only for "crc"')

    message = 'Checksum "bitorder" must be "lsb" or "msb"'
    bitorder = _optional_string(spec, "bitorder", message)
    if bitorder is not None and bitorder not in ("lsb", "msb"):
        raise EncodeError(message)
    msb_first = bitorder == "msb"

    message = 'Checksum "bits" must be two different symbols, e.g. "01"'
    bits = _optional_string(spec, "bits", message)
    if bits is not None and (len(bits) != 2 or bits[0] == bits[1]):
        raise EncodeError(message)
    zero, one = (bits[0], bits[1]) if bits else ("0", "1")

    message = 'Checksum "restart" must be a string of symbols that are not bits'
    restart = _optional_string(spec, "restart", message)
    if restart is not None and (zero in restart or one in restart):
        raise EncodeError(message)

    units = _covered_units(spec)

    # Positions of the bit symbols in the code, without the bits of a partial
    # unit before a restart symbol
    positions: list[int] = []
    fill = 0
    for i, symbol in enumerate(code):
        if symbol in (zero, one):
            positions.append(i)
            fill = (fill + 1) % width
        elif restart and symbol in restart:
            if fill:
                del positions[-fill:]
            fill = 0
    unit_count = len(positions) // width

    last = 0
    for k, unit_at in enumerate(at):
        last = max(last, unit_at)
        if unit_at in at[:k]:
            raise EncodeError(f"Checksum writes {unit_name} {unit_at} twice")
        if unit_at in units:
            raise EncodeError(f"Checksum {unit_name} {unit_at} is one of the {unit_name}s it covers")
    last = max([last, *units])
    if last >= unit_count:
        raise EncodeError(f"Checksum uses {unit_name} {last}, but the code has {unit_count} {unit_name}s")

    def read_unit(index: int) -> int:
        value = 0
        for i in range(width):
            if code[positions[index * width + i]] == one:
                value |= 1 << (width - 1 - i if msb_first else i)
        return value

    value = _reflect(init, result_width) if kind == "crc" and reflected else init
    for index in units:
        u = read_unit(index)
        if kind == "sum":
            value = (value + u) & _U32
        elif kind == "xor":
            value ^= u
        elif kind == "popcount":
            value = (value + bin(u).count("1")) & _U32
        else:
            value = _crc_unit(value, u, width, poly, result_width, reflected, mask)
    if invert:
        value = ~value & _U32
    if negate:
        value = -value & _U32
    value = (value ^ xorout) & mask

    # The units of "at" hold the result in the bit order: with "lsb" the first
    # unit holds the lowest bits, with "msb" the highest
    for k, unit_at in enumerate(at):
        shift = width * (len(at) - 1 - k if msb_first else k)
        part = (value >> shift) & ((1 << width) - 1)
        for i in range(width):
            bit = part & (1 << (width - 1 - i if msb_first else i))
            code[positions[unit_at * width + i]] = one if bit else zero


def apply_checksums(checksums: Any, code: str) -> str:
    """The code with a remote's "checksums" applied, in order."""
    if not isinstance(checksums, list):
        return code
    symbols = list(code)
    for index, spec in enumerate(checksums):
        if not isinstance(spec, dict):
            raise EncodeError(f"Checksum {index} is not an object")
        _apply_checksum(spec, symbols)
    return "".join(symbols)


# Plugins (plugins.c, hvac_panasonic_plugin.c)


def _hvac_panasonic(code: str) -> str:
    """Panasonic's checksum: 0xF4 plus the first 26 bytes, sent lowest bit first,
    into the byte after them. Symbols other than 0 and 1 are skipped."""
    symbols = list(code)
    index = 0

    def skip() -> None:
        nonlocal index
        while index < len(symbols) and symbols[index] not in ("0", "1"):
            index += 1

    checksum = 0b11110100
    for _ in range(26):
        skip()
        byte = 0
        for i in range(8):
            if index + i < len(symbols) and symbols[index + i] == "1":
                byte |= 1 << i
        index += 8
        checksum = (checksum + byte) & 0xFF
    skip()
    for i in range(8):
        if index + 7 - i < len(symbols):
            symbols[index + 7 - i] = "1" if (checksum << i) & 0x80 else "0"
    return "".join(symbols)


def apply_plugin(plugin: str | None, code: str) -> str:
    """The code after the remote's plugin, if it has one."""
    if plugin is None:
        return code
    if plugin == "hvac_panasonic":
        return _hvac_panasonic(code)
    raise EncodeError(f"Unknown plugin {plugin}")


# Pulses (pulses.c)


def build_timings(symbols: list[tuple[str, int, int]], code: str) -> list[int]:
    """Alternating pulse (positive) and space (negative) durations in
    microseconds, starting and ending with a pulse; a pulse or space following
    one of its kind is merged with it, as the kernel's IR drivers and ESPHome's
    remote_transmitter take them."""
    definitions: dict[str, tuple[int, int]] = {}
    for symbol, mark, space in symbols:
        definitions[symbol] = (mark, space)  # the last definition of a symbol wins
    values: list[int] = []

    def add(pulse: bool, duration: int) -> None:
        if duration == 0:
            return
        if not values and not pulse:
            return  # a space cannot come first
        if values and (len(values) % 2 == 1) == pulse:
            values[-1] += duration
            return
        if len(values) >= MAX_PULSE_VALUES:
            raise EncodeError(f"Code needs more than {MAX_PULSE_VALUES} pulses and spaces")
        values.append(duration)

    for symbol in code:
        if symbol not in definitions:
            raise EncodeError(f"Undefined symbol '{symbol}'")
        mark, space = definitions[symbol]
        add(True, mark)
        add(False, space)
    # The signal must end with a pulse
    if values and len(values) % 2 == 0:
        values.pop()
    if not values:
        raise EncodeError("Nothing to transmit")
    return [value if i % 2 == 0 else -value for i, value in enumerate(values)]


def repeat_timings(timings: list[int], times: int, wait: int) -> list[int]:
    """The timings sent times times, with wait microseconds between them."""
    result = list(timings)
    for _ in range(times - 1):
        if wait > 0:
            result.append(-wait)
            result.extend(timings)
        else:
            result[-1] += timings[0]  # two pulses in a row are one pulse
            result.extend(timings[1:])
    return result
