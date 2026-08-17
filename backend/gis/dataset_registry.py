"""Dataset registry. Deprecated mappings cannot be selected silently."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / "data" / "gis" / "registry.json"

DEPRECATED_CARLSWALD_NORTH_001 = "carlswald_north_001"
CORRECT_CARLSWALD_NORTH = "carlswald_north_corrected_001"
# Frozen EXT.6 + EXT.13 universe used by PR #15 / PR #16. Do not overwrite.
FROZEN_CARLSWALD_NORTH_001 = CORRECT_CARLSWALD_NORTH
# Complete intended Carlswald North: Summerset EXT.3 + EXT.6 + EXT.13.
COMPLETE_CARLSWALD_NORTH = "carlswald_north_corrected_002"


class DeprecatedDatasetError(RuntimeError):
    """Raised when code tries to use a blocked incorrect estate mapping."""


def load_registry(path: Path | None = None) -> dict:
    registry_path = path or DEFAULT_REGISTRY
    return json.loads(registry_path.read_text(encoding="utf-8"))


def find_datasets_for_estate(estate_name: str, path: Path | None = None) -> list[dict]:
    """Return active datasets for an estate. Deprecated mappings are never returned."""
    wanted = (estate_name or "").strip().lower()
    aliases = {
        "carlswald north estate": "carlswald north",
        "carlswald north": "carlswald north",
    }
    key = aliases.get(wanted, wanted)
    matches = []
    for item in load_registry(path).get("datasets", []):
        if item.get("deprecated") or item.get("status") == "incorrect":
            blocked = [name.lower() for name in item.get("do_not_use_for_estates") or []]
            if wanted in blocked or key in blocked:
                continue
            continue
        names = [name.lower() for name in item.get("estate_names") or []]
        if wanted in names or key in names:
            matches.append(item)
    return matches


def require_active_dataset(dataset_id: str, path: Path | None = None) -> dict:
    for item in load_registry(path).get("datasets", []):
        if item.get("dataset_id") != dataset_id:
            continue
        if item.get("deprecated") or item.get("status") == "incorrect":
            raise DeprecatedDatasetError(
                f"{dataset_id} is marked incorrect/deprecated and cannot be used. "
                f"reason={item.get('reason')} replaced_by={item.get('replaced_by')}"
            )
        return item
    raise KeyError(f"Unknown dataset_id {dataset_id}")
