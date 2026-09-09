"""Fail-closed access controls for the V4D neutral portable benchmark."""

from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parent
NEUTRAL_ROOT = PACKAGE_ROOT / "controls"
FORBIDDEN_IDENTIFIERS = frozenset({"117539389", "117255083"})
ALLOWED_CONTROLS = frozenset(
    {
        "controls/coloured_shapes.png",
        "controls/neutral_multiview_a.png",
        "controls/neutral_multiview_b.png",
        "controls/unlabelled_property_schematic.png",
    }
)
GLOB_METACHARACTERS = frozenset("*?[]{}")


class UnsafeBenchmarkInput(ValueError):
    """Raised when an input cannot be proven to be an explicit neutral control."""


def _normalized_relative_path(value: str | Path) -> PurePosixPath:
    text = str(value).replace("\\", "/")
    if any(character in text for character in GLOB_METACHARACTERS):
        raise UnsafeBenchmarkInput("glob and pattern inputs are forbidden")
    if any(identifier in text for identifier in FORBIDDEN_IDENTIFIERS):
        raise UnsafeBenchmarkInput("forbidden listing identifier in input")

    path = PurePosixPath(text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise UnsafeBenchmarkInput("input must be a simple relative path")
    return path


def _has_linked_component(path: Path) -> bool:
    current = NEUTRAL_ROOT
    for part in path.relative_to(NEUTRAL_ROOT).parts:
        current = current / part
        if current.is_symlink() or os.path.isjunction(current):
            return True
    return False


def validate_control_path(value: str | Path) -> Path:
    """Return a control only when it is a named, non-linked file in this package."""
    relative = _normalized_relative_path(value)
    normalized = relative.as_posix()
    if normalized not in ALLOWED_CONTROLS:
        raise UnsafeBenchmarkInput("input is not an explicitly allow-listed neutral control")

    candidate = PACKAGE_ROOT.joinpath(*relative.parts)
    if NEUTRAL_ROOT.is_symlink() or os.path.isjunction(NEUTRAL_ROOT) or _has_linked_component(candidate):
        raise UnsafeBenchmarkInput("symlinks and junctions are forbidden")
    canonical_root = NEUTRAL_ROOT.resolve(strict=True)
    canonical_candidate = candidate.resolve(strict=True)
    if not canonical_candidate.is_relative_to(canonical_root) or not canonical_candidate.is_file():
        raise UnsafeBenchmarkInput("input escapes the neutral control root")
    return canonical_candidate


def validate_manifest(manifest: dict[str, Any]) -> list[Path]:
    """Validate explicit manifest entries without scanning any directories."""
    controls = manifest.get("controls")
    if not isinstance(controls, list) or not controls:
        raise UnsafeBenchmarkInput("manifest must contain a non-empty controls list")
    if set(manifest) - {"benchmark_version", "controls", "prompts", "acceptance"}:
        raise UnsafeBenchmarkInput("manifest contains unsupported fields")
    if not all(isinstance(item, str) for item in controls):
        raise UnsafeBenchmarkInput("manifest control entries must be strings")
    if len(set(controls)) != len(controls):
        raise UnsafeBenchmarkInput("manifest control entries must be unique")
    return [validate_control_path(item) for item in controls]


def load_manifest(path: str | Path = "benchmark_manifest.json") -> dict[str, Any]:
    """Load the package manifest only after validating its explicit control entries."""
    manifest_path = _normalized_relative_path(path)
    if manifest_path.as_posix() != "benchmark_manifest.json":
        raise UnsafeBenchmarkInput("only the packaged benchmark manifest is allowed")
    source = PACKAGE_ROOT.joinpath(*manifest_path.parts)
    if source.is_symlink() or os.path.isjunction(source):
        raise UnsafeBenchmarkInput("manifest links are forbidden")
    manifest = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise UnsafeBenchmarkInput("manifest root must be an object")
    validate_manifest(manifest)
    return manifest
