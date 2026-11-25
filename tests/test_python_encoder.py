#!/usr/bin/env python3
"""The Home Assistant integration's Python encoder sends what the C core sends.

usage: test_python_encoder.py [--reference ENCODE_REFERENCE] [REMOTE.json...]

Checks every remote in conf/remotes (or the ones given):
- each test vector ("tests") gives its outcome, unless listed in
  tests/known_failures.txt
- with --reference (tests/encode_reference.c), the code and the pulses of the
  template, of every value of every feature (also toggled, for remotes with a
  toggle bit) and of every test vector are those of the C core, or both fail

Only Python's standard library is needed.
"""

import argparse
import json
import logging
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "custom_components" / "irlingo"))

from encoder import EncodeError, Remote  # noqa: E402


def known_failures():
    lines = (ROOT / "tests" / "known_failures.txt").read_text().splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


def python_output(remote, features, toggled):
    try:
        code = remote.encode(features, toggled)
        return code + "|" + ",".join(str(t) for t in remote.timings(code))
    except EncodeError:
        return "ERROR"


def check_vectors(path, remote, data, known):
    """Test vectors failing that are not known failures"""
    name = str(path.relative_to(ROOT / "conf" / "remotes").with_suffix(""))
    failures = []
    for test in data.get("tests", []):
        wanted = test.get("features", {})
        ok = False
        if all(isinstance(v, str) and remote.has_feature(k, v) for k, v in wanted.items()):
            try:
                ok = remote.encode(wanted) == test.get("outcome")
            except EncodeError:
                ok = False
        if not ok and f"{name}: {test.get('description')}" not in known:
            failures.append(f"{name}: {test.get('description')}")
    return len(data.get("tests", [])), failures


def requests_for(remote, data):
    requests = [({}, False)]
    for name, values in remote.features.items():
        for value in values:
            requests.append(({name: value}, False))
            if remote.has_toggle:
                requests.append(({name: value}, True))
    for test in data.get("tests", []):
        features = test.get("features", {})
        if all(isinstance(v, str) for v in features.values()):
            requests.append((features, False))
    # The reference reads tab-separated NAME=VALUE pairs
    return [
        (features, toggled)
        for features, toggled in requests
        if not any(c in k + v for k, v in features.items() for c in "\t\r\n=")
    ]


def check_reference(path, remote, data, reference):
    """Requests whose code or pulses differ from the C core's"""
    requests = requests_for(remote, data)
    stdin = "".join(
        str(int(toggled)) + "".join(f"\t{k}={v}" for k, v in features.items()) + "\n" for features, toggled in requests
    )
    result = subprocess.run([reference, str(path)], input=stdin, capture_output=True, text=True, check=False)
    lines = result.stdout.splitlines()
    if result.returncode != 0 or len(lines) != len(requests):
        return len(requests), [f"{path}: the reference failed ({result.stderr.strip()})"]
    differences = []
    for (features, toggled), expected in zip(requests, lines, strict=True):
        got = python_output(remote, features, toggled)
        if got != expected:
            differences.append(
                f"{path}: {features} toggled={toggled}\n  C:      {expected[:200]}\n  Python: {got[:200]}"
            )
    return len(requests), differences


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--reference", help="tests/encode_reference built")
    parser.add_argument("remotes", nargs="*", type=Path)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)

    paths = [p.resolve() for p in args.remotes] or sorted((ROOT / "conf" / "remotes").glob("*/*.json"))
    known = known_failures()
    vectors = compared = 0
    problems = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        remote = Remote(data, str(path))
        count, failures = check_vectors(path, remote, data, known)
        vectors += count
        problems += failures
        if args.reference:
            count, differences = check_reference(path, remote, data, args.reference)
            compared += count
            problems += differences

    for problem in problems[:20]:
        print("FAIL", problem)
    print(
        f"{len(paths)} remotes, {vectors} test vectors"
        + (f", {compared} codes compared with the C core" if args.reference else "")
        + f": {len(problems)} problems"
    )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
