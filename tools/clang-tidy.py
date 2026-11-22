#!/usr/bin/env python3
"""Run clang-tidy with ESPHome's checks (.clang-tidy) on the ESPHome component.

usage: tools/clang-tidy.py [--fix] [--c] [FILE...]

The checks need the component compiled for the ESP32 by ESPHome, which
writes a compilation database: run tests/esphome/check.sh --compile (or
esphome compile tests/esphome/full.yaml) first. clang-tidy 23, the version
ESPHome uses, must be installed (pip install clang-tidy==23.1.4).

By default the component's C++ files are checked; --c also checks the
portable C core, which ESPHome's C++ naming rules do not fit. FILE limits the
check to these files. --fix applies clang-tidy's fixes to the files in the
repository.

The ESP32 compiler's flags are turned into clang's the way ESPHome's own
script/clang-tidy does: clang has no ESP32 core configuration, so the code is
analysed in 32-bit x86 mode with the Xtensa macros defined.
"""

import argparse
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "components" / "irlingo"
BUILD = ROOT / "tests" / "esphome" / ".esphome" / "build" / "irlingo-test"
DATABASE = BUILD / "build" / "compile_commands.json"
BUILD_COMPONENT = BUILD / "src" / "esphome" / "components" / "irlingo"
# Code copied from other projects keeps its own style
SKIP = {"parson.c"}
# The portable C core's headers: a C API, which ESPHome's C++ naming rules
# do not fit (checked with --c)
C_HEADERS = r".*/components/irlingo/(checksum|irremote|log|parson|plugins|pulses|symboldefinition|hvac_panasonic_plugin)\.h"

# GCC flags clang does not understand (from ESPHome's script/clang-tidy)
OMIT_FLAGS = {
    "-free",
    "-fipa-pta",
    "-fstrict-volatile-bitfields",
    "-mlongcalls",
    "-mtext-section-literals",
    "-mdisable-hardware-atomics",
    "-mfix-esp32-psram-cache-issue",
    "-mfix-esp32-psram-cache-strategy=memw",
    "-fno-tree-switch-conversion",
    "-freorder-blocks",
    "-fno-jump-tables",
    "-fno-shrink-wrap",
    "-mno-target-align",
}

EXTRA_FLAGS = [
    "-m32",
    "-U__i386__",
    "-U__x86_64__",
    "-D__XTENSA__",
    "-D__XTENSA_EL__",
    "-D_LIBC",
    "-nostdinc",
    "-DCLANG_TIDY",
    "-D_GLIBCXX_HAVE_TLS",
    "-Ddeprecated(x)=",
    "-D_PGMSPACE_H_",
    "-Dpgm_read_byte(s)=(*(const uint8_t *)(s))",
    "-DPROGMEM=",
    "-DPGM_P=const char *",
    "-DPSTR(s)=(s)",
]


def system_includes(compiler, language):
    """The include directories the ESP32 compiler searches by itself"""
    result = subprocess.run(
        [compiler, "-E", "-x", language, "-", "-v"],
        input="",
        capture_output=True,
        text=True,
        check=True,
    )
    lines = result.stderr.splitlines()
    start = lines.index("#include <...> search starts here:") + 1
    end = lines.index("End of search list.")
    return [line.strip() for line in lines[start:end]]


def clang_arguments(entry, includes):
    """The clang arguments for one compile command of the ESP32 build"""
    args = entry["arguments"] if "arguments" in entry else shlex.split(entry["command"])
    # ESP-IDF passes the toolchain's flags in response files (@file)
    args = [
        expanded
        for arg in args
        for expanded in (shlex.split(Path(arg[1:]).read_text()) if arg.startswith("@") else [arg])
    ]
    cpp = entry["file"].endswith(".cpp")
    result = ["clang++" if cpp else "clang"] + EXTRA_FLAGS
    if cpp:
        result += ["-nostdinc++", "-std=gnu++20", "-fno-cxx-modules"]
    skip_next = False
    for i, arg in enumerate(args[1:], 1):
        if skip_next:
            skip_next = False
        elif arg == "-o":
            skip_next = True
        elif arg == "-include" and i + 1 < len(args) and "cmake_pch" in args[i + 1]:
            # GCC's precompiled header, which clang cannot read
            skip_next = True
        elif arg in ("-c", "-Winvalid-pch", entry["file"]) or arg in OMIT_FLAGS:
            pass
        elif arg.startswith(("-Werror", "-mtune=esp")) or (cpp and arg.startswith("-std=")):
            pass
        else:
            result.append(arg)
    for directory in includes["c++" if cpp else "c"]:
        result += ["-isystem", directory]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--fix", action="store_true", help="apply clang-tidy's fixes")
    parser.add_argument("--c", action="store_true", help="also check the portable C core")
    parser.add_argument("files", nargs="*", type=Path, help="only these files")
    args = parser.parse_args()

    if not DATABASE.is_file():
        sys.exit(f"{DATABASE} not found: run tests/esphome/check.sh --compile first")
    clang_tidy = shutil.which("clang-tidy")
    if not clang_tidy:
        sys.exit("clang-tidy not found: pip install clang-tidy==23.1.4")

    wanted = {path.resolve() for path in args.files}
    entries = []
    for entry in json.loads(DATABASE.read_text()):
        path = Path(entry["file"])
        if BUILD_COMPONENT not in path.parents or path.name in SKIP:
            continue
        # The repository's file, not ESPHome's copy, so findings and fixes
        # are where they belong
        source = COMPONENT / path.relative_to(BUILD_COMPONENT)
        if path.suffix == ".c" and not args.c and source not in wanted:
            continue
        if wanted and source not in wanted:
            continue
        entries.append((entry, source))
    if not entries:
        sys.exit("No files to check")

    args0 = entries[0][0]
    compiler = (args0["arguments"] if "arguments" in args0 else shlex.split(args0["command"]))[0]
    includes = {
        "c": system_includes(compiler, "c"),
        "c++": system_includes(compiler.replace("-gcc", "-g++"), "c++"),
    }

    with tempfile.TemporaryDirectory() as directory:
        database = [
            {
                "directory": entry["directory"],
                "file": str(source),
                "arguments": clang_arguments(entry, includes) + ["-c", str(source)],
            }
            for entry, source in entries
        ]
        Path(directory, "compile_commands.json").write_text(json.dumps(database))
        command = [
            clang_tidy,
            "-p",
            directory,
            f"--config-file={ROOT / '.clang-tidy'}",
            f"--header-filter={COMPONENT}/.*",
            "--quiet",
        ]
        if not args.c:
            command.append(f"--exclude-header-filter={C_HEADERS}")
        if args.fix:
            command.append("--fix")
        failed = False
        for _, source in entries:
            print(f"clang-tidy {source.relative_to(ROOT)}", flush=True)
            failed |= subprocess.run(command + [str(source)], check=False).returncode != 0
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
