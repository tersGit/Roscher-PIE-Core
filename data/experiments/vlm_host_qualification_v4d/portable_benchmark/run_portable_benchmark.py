#!/usr/bin/env python3
"""Print the deterministic, neutral V4D benchmark worklist after fail-closed validation."""

from __future__ import annotations

import argparse
import json

from portable_benchmark import load_manifest, validate_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="benchmark_manifest.json")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    controls = validate_manifest(manifest)
    print(json.dumps(
        {
            "controls": [str(path) for path in controls],
            "prompts": manifest["prompts"],
            "acceptance": manifest["acceptance"],
            "instruction": "Run each listed control only with the listed prompts; preserve raw output and timing.",
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
