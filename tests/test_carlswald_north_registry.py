from backend.gis.dataset_registry import (
    DEPRECATED_CARLSWALD_NORTH_001,
    DeprecatedDatasetError,
    find_datasets_for_estate,
    require_active_dataset,
)


def test_carlswald_north_001_cannot_be_selected():
    matches = find_datasets_for_estate("Carlswald North Estate")
    ids = [item["dataset_id"] for item in matches]
    assert DEPRECATED_CARLSWALD_NORTH_001 not in ids
    assert "carlswald_north_corrected_001" in ids


def test_require_active_blocks_deprecated_mapping():
    try:
        require_active_dataset(DEPRECATED_CARLSWALD_NORTH_001)
    except DeprecatedDatasetError as exc:
        assert "incorrect" in str(exc).lower() or "deprecated" in str(exc).lower()
    else:
        raise AssertionError("deprecated dataset was selectable")
