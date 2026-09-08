import json

from scripts.lvi_v1 import _classify, _text_evidence
from backend.parsers.property24 import ListingData


def test_classification_is_multi_label_and_does_not_assign_structure():
    labels, method = _classify(
        {"green_fraction": 0.2, "cyan_fraction": 0.05, "dark_fraction": 0.2,
         "bright_fraction": 0.1, "upper_luma": 80, "lower_luma": 120},
        1600,
        900,
    )
    assert "GARDEN" in labels
    assert "POOL" in labels
    assert "ROOF_VISIBLE" in labels
    assert method


def test_text_does_not_create_visual_provenance():
    listing = ListingData(listing_id="x", listing_url="u", description="solar panels and inverter")
    evidence = _text_evidence(listing)
    assert {item["feature"] for item in evidence} == {"solar", "backup_power"}
    assert all(item["provenance"] == "LISTING_TEXT" for item in evidence)


def test_schema_is_json_object():
    schema = json.loads(
        open(
            "data/experiments/listing_visual_intelligence_v1/LVI_V1_SCHEMA.json",
            encoding="utf-8",
        ).read()
    )
    assert schema["title"] == "Listing Visual Intelligence v1"
    assert "target_property" in schema["properties"]
