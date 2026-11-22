# Development

- [Source layout](#source-layout)
- [Building and testing](#building-and-testing)
- [Coverage](#coverage)
- [Continuous integration](#continuous-integration)
- [Adding a remote to irlingo](#adding-a-remote-to-irlingo)
- [Releases](#releases)

## Source layout

The code is in two parts. `components/irlingo/` holds the portable core, which
also an ESPHome component for the ESP32 will compile: it must not use anything
specific to Linux. `src/` holds the Linux parts: the command line, finding
installed remotes, the toggle state file and the transmitter backends. CMake
builds them as the libraries `irlingo_core` and `irlingo_linux`, with `src/log.c` as
`irlingo_log`.

| Path | Contents |
|------|----------|
| `components/irlingo/irremote.c` | a remote, parsed from a file or from text, as a handle (`irRemote`): symbols, template, features, overrides, variants, toggle; encoding a code into a buffer the caller gives, without allocating |
| `components/irlingo/checksum.c` | the declarative `checksums` |
| `components/irlingo/pulses.c` | turning a code into pulse and space durations |
| `components/irlingo/plugins.c`, `components/irlingo/hvac_panasonic_plugin.c` | remote plugins |
| `components/irlingo/parson.c` | the JSON parser |
| `components/irlingo/log.h` | log messages: `log_log()` comes from `src/log.c` on Linux and `irlingo_log.cpp` in ESPHome |
| `src/irlingo.c` | the command line |
| `src/config.c` | the command's one loaded remote (`loadConfig()` and friends), on top of `irremote.c` |
| `src/log.c` | logging on Linux (rxi's log.c) |
| `src/remotes.c` | finding remotes by name |
| `src/lirc.c`, `src/transmitter.c`, `src/irslinger.c` | the `lirc`, `gpiod` and `pigpio` backends |
| `src/state.c` | the toggle state file |
| `conf/remotes/` | the remotes |
| `tools/lirc2irlingo.py` | the LIRC converter |
| `tools/ir2irlingo.py` | derives remotes from recorded codes |
| `tools/heatpumpir/` | records arduino-heatpumpir codes as captures |
| `tools/irlingo-remotes.in` | the `irlingo-remotes` command |
| `cmake/` | toolchain files, remote selection, packaging |
| `tests/` | unit and command line tests |

## Building and testing

```
cmake -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

The tests cover the configuration loader, remote lookup, checksums, the plugins, the transmitter backend selected at configure time, the `irlingo` command line, `irlingo-remotes`, the LIRC converter and `ir2irlingo.py`, which must derive `panasonic/hvac_panasonic` again from the codes it sends. Every key of every remote in `conf/remotes/` is checked to produce a code irlingo can send, and every [test vector](remote-format.md#tests) of every remote is checked. Vectors that do not match yet are listed in `tests/known_failures.txt`.

No test transmits IR, so they are safe to run on a Pi. The backends are tested against simulated drivers and libraries: the `ioctl` and `write` calls of the `lirc` backend, libgpiod and pigpio are replaced when linking the tests.

The Python tests need only Python 3; run one directly with:
```
cd tests && PYTHONPATH=../tools python3 -m unittest test_ir2irlingo
```

`build/tests/encode_remote REMOTE.json` prints the codes irlingo builds for feature sets read from standard input, one `NAME=VALUE ...` line each, without transmitting.

When cross compiling, tests run under qemu if you add e.g. `-DCMAKE_CROSSCOMPILING_EMULATOR=$(command -v qemu-aarch64)` (package `qemu-user`).

## Coverage

```
cmake -B build-coverage -DIRLINGO_COVERAGE=ON
cmake --build build-coverage
ctest --test-dir build-coverage
gcovr -r . build-coverage --exclude 'components/irlingo/parson\..*' --exclude 'tests/'
```

The converters are measured too when Python's `coverage` module is installed. CI requires 95% line coverage of the C code and of the converters.

## ESPHome component

`tests/esphome/check.sh` checks the [ESPHome component](esphome.md) with ESPHome
installed (`pip install esphome`): `tests/esphome/full.yaml`, which uses every
part of the component, must be valid, and variants of it with mistakes must fail
with the expected messages. With `--compile` it also compiles `full.yaml` and
`doc/examples/esphome-irlingo.yaml` for ESP32, and since 3.3.0
`tests/esphome/platforms/*.yaml` for the ESP32-S3, -C3, -C6, ESP8266 and
RP2040, printing the RAM and flash use of each (the first time, ESPHome
downloads the toolchains). To add a chip, add a small YAML file there with its
`esp32:`, `esp8266:` or `rp2040:` block that includes `common.yaml`.

```
tests/esphome/check.sh --compile
```

The component's C++ and Python files are only compiled by ESPHome, not by the
CMake build.

## Code style

The C and C++ code follows ESPHome's style, set by `.clang-format` (taken from
ESPHome): two spaces, no tabs, 120 columns. Code copied from other projects
(parson, rxi's log.c) keeps its own style and is listed in
`.clang-format-ignore`. CI checks the formatting with clang-format 23.1.3, the
version ESPHome uses:

```
pip install clang-format==23.1.3
git ls-files '*.c' '*.h' '*.cpp' | xargs clang-format -i
```

The ESPHome component's C++ is also checked with ESPHome's clang-tidy checks
(`.clang-tidy`, taken from ESPHome). They need the compilation database of an
ESP32 build, so compile the component first:

```
pip install clang-tidy==23.1.4
tests/esphome/check.sh --compile
tools/clang-tidy.py            # --fix applies the fixes clang-tidy offers
```

The portable C core is left out: ESPHome's C++ naming rules do not fit its C
API. `tools/clang-tidy.py --c` checks it too.

The commit that reformatted the code is in `.git-blame-ignore-revs`; to have
`git blame` skip it locally, run
`git config blame.ignoreRevsFile .git-blame-ignore-revs`.

## API documentation

The C and C++ code is documented with Doxygen, as ESPHome's is: comments
written `///` before a declaration in a header become the API reference,
whose front page is `doc/api.md`. The `Doxyfile` has ESPHome's settings; it
needs Doxygen 1.12 or newer (Ubuntu packages 1.9.8, so CI downloads Doxygen's
own build). A broken documentation comment fails the build, while undocumented
code is fine.

```
cmake -B build -DIRLINGO_DOCS=ON    # or build the target docs on its own
cmake --build build                 # HTML in build/docs/api-docs
```

`cmake --build build --target docs_archive` packs the HTML into
`irlingo-api-docs-<version>.tar.gz`, which CI builds on every run and attaches
to releases. The documentation of `master` is published on GitHub Pages:
<https://mortenmathiasen.github.io/irlingo/>.

## Continuous integration

GitHub Actions runs the tests for all three backends, with AddressSanitizer and UndefinedBehaviorSanitizer, measures coverage, runs the tests of the `armv6`, `armv7` and `aarch64` builds under qemu, checks the formatting with clang-format, builds the API documentation (and publishes that of `master` on GitHub Pages), and runs
`tests/esphome/check.sh --compile` with the ESPHome version given in the
workflow, followed by `tools/clang-tidy.py`. A separate workflow converts the LIRC database again with `tools/lirc2irlingo.py` and fails if `conf/remotes` differs from the result, and compares the converter with LIRC's own `irsimsend`.

## Adding a remote to irlingo

1. Put it in `conf/remotes/<manufacturer>/<name>.json`. Remotes made for irlingo have no `source` setting; files with `source` are replaced by the LIRC conversion check.
2. Add `tests`: codes recorded from the real remote (or the protocol's reference implementation), with the features they were sent for.
3. To ship it in the release packages, name it `hvac_<model>.json`: since 3.3.0, `native` in `cmake/remotes.cmake` selects irlingo's own remotes by that name.
4. Run the tests.

The 44 air conditioner remotes for arduino-heatpumpir's models were derived with `tools/heatpumpir` and `ir2irlingo`; to derive one again, e.g. after a change in the library, see [Air conditioners supported by arduino-heatpumpir](remotes.md#air-conditioners-supported-by-arduino-heatpumpir).

## Releases

Update `VERSION` in `CMakeLists.txt`, commit, and push a matching signed tag:
```
git commit -S -m "Release 3.3.0"
git tag -s v3.3.0 -m "irlingo 3.3.0"
git push origin master v3.3.0
```

GitHub Actions then runs all tests, builds the packages for every Raspberry Pi architecture, the archive of all remotes (`irlingo-remotes-<version>.tar.gz`) and the API documentation (`irlingo-api-docs-<version>.tar.gz`), and publishes them with checksums as a GitHub release.

The release commit and tag are signed, so GitHub shows them as verified. This
needs a signing key: with an SSH key, set git up once

```
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519.pub
git config --global commit.gpgsign true   # sign every commit, then -S is not needed
git config --global tag.gpgsign true      # sign every annotated tag, then -s is not needed
```

and add the same public key to your GitHub account as a **signing key**
(Settings, SSH and GPG keys, or
`gh ssh-key add ~/.ssh/id_ed25519.pub --type signing`). To check a signature
locally, list your key in an allowed signers file
(`git config --global gpg.ssh.allowedSignersFile ~/.ssh/allowed_signers`) and
run `git verify-tag v3.3.0`.
