#!/usr/bin/env python3
"""Pack the Home Assistant integration for HACS: irlingo-homeassistant.zip.

usage: package_homeassistant.py --version VERSION --out ZIP

The zip holds custom_components/irlingo/ and, in its remotes/ directory, every
remote in conf/remotes without its test vectors, minified. HACS installs the
zip of a release into custom_components/irlingo/ (hacs.json: zip_release).
The integration's manifest must have the version being released.
"""

import argparse
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
INTEGRATION = ROOT / "custom_components" / "irlingo"
REMOTES = ROOT / "conf" / "remotes"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--version", required=True, help="the version being released")
    parser.add_argument("--out", required=True, type=Path, help="the zip to write")
    args = parser.parse_args()

    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != args.version:
        sys.exit(f"custom_components/irlingo/manifest.json has version {manifest.get('version')}, not {args.version}")

    files = remotes = 0
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(INTEGRATION.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                archive.write(path, path.relative_to(INTEGRATION).as_posix())
                files += 1
        for path in sorted(REMOTES.glob("*/*.json")):
            remote = json.loads(path.read_text(encoding="utf-8"))
            remote.pop("tests", None)
            name = "remotes/" + path.relative_to(REMOTES).as_posix()
            archive.writestr(name, json.dumps(remote, separators=(",", ":"), ensure_ascii=False))
            remotes += 1
    print(f"{args.out}: {files} integration files, {remotes} remotes")


if __name__ == "__main__":
    main()
