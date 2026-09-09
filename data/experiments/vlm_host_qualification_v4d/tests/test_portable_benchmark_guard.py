import json
from pathlib import Path

import pytest

import data.experiments.vlm_host_qualification_v4d.portable_benchmark.portable_benchmark as guard
from data.experiments.vlm_host_qualification_v4d.portable_benchmark.portable_benchmark import (
    UnsafeBenchmarkInput,
    load_manifest,
    validate_control_path,
    validate_manifest,
)


def test_all_packaged_manifest_controls_are_explicitly_allowed():
    manifest = load_manifest()
    paths = validate_manifest(manifest)
    assert {path.name for path in paths} == {
        "coloured_shapes.png",
        "neutral_multiview_a.png",
        "neutral_multiview_b.png",
        "unlabelled_property_schematic.png",
    }
    assert all(path.is_file() for path in paths)


@pytest.mark.parametrize(
    "value",
    [
        "controls/*.png",
        "controls/**/neutral_multiview_a.png",
        "../117539389/image.png",
        "controls/117255083.png",
        "C:\\117539389\\image.png",
        "controls/unapproved.png",
    ],
)
def test_guard_rejects_globs_traversal_forbidden_ids_and_unknown_controls(value):
    with pytest.raises(UnsafeBenchmarkInput):
        validate_control_path(value)


def test_guard_rejects_manifest_indirection_and_forbidden_entries():
    with pytest.raises(UnsafeBenchmarkInput):
        validate_manifest({"controls": ["controls/**/neutral_multiview_a.png"]})
    with pytest.raises(UnsafeBenchmarkInput):
        validate_manifest({"controls": ["controls/coloured_shapes.png", "../117255083/control.png"]})
    with pytest.raises(UnsafeBenchmarkInput):
        validate_manifest({"controls": ["controls/coloured_shapes.png"], "recursive": True})


def test_guard_accepts_only_its_packaged_manifest():
    with pytest.raises(UnsafeBenchmarkInput):
        load_manifest("controls/coloured_shapes.png")
    with pytest.raises(UnsafeBenchmarkInput):
        load_manifest(Path("elsewhere.json"))
    assert json.loads(Path("data/experiments/vlm_host_qualification_v4d/portable_benchmark/benchmark_manifest.json").read_text())[
        "benchmark_version"
    ] == "V4C-portable-neutral-unchanged"


def test_guard_rejects_a_symlink_or_junction_before_canonicalizing(monkeypatch):
    monkeypatch.setattr(guard, "_has_linked_component", lambda path: True)
    with pytest.raises(UnsafeBenchmarkInput, match="symlinks and junctions"):
        guard.validate_control_path("controls/coloured_shapes.png")
