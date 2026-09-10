from scripts.build_waterfall_country_estate_gis import deduplicate, feature_from_row, normalized_name, official_name


def _row(stand: str = "1", property_id: int = 1) -> dict:
    return {
        "attributes": {
            "PROPERTY_ID": property_id, "OBJECTID": property_id, "SG_ID": f"sg-{property_id}",
            "STAND_NO": stand, "TOWN_NAME_DESC": "JUKSKEI VIEW EXT.19", "AREA_SQMT": 1000,
            "LAND_TYPE_NAME": "Erven", "CAT_DESC": "Residential", "ZONING": "Residential 1",
        },
        "geometry": {"rings": [[[28.1, -26.0], [28.101, -26.0], [28.101, -26.001], [28.1, -26.0]]]},
    }


def test_waterfall_names_are_exact_and_normalized():
    assert official_name(105) == "JUKSKEI VIEW EXT.105"
    assert normalized_name(105) == "JUKSKEI VIEW EXTENSION 105"


def test_waterfall_feature_preserves_source_and_gis_identifiers():
    feature = feature_from_row(_row(), 19)
    props = feature["properties"]
    assert props["township_source"] == "JUKSKEI VIEW EXT.19"
    assert props["township_normalized"] == "JUKSKEI VIEW EXTENSION 19"
    assert props["pie_property_id"] == 1
    assert props["sg_id"] == "sg-1"
    assert props["centroid_latitude"] is not None


def test_duplicate_extension_stand_is_flagged_not_silently_removed():
    one = feature_from_row(_row("12", 1), 19)
    two = feature_from_row(_row("12", 2), 19)
    rows, duplicates = deduplicate([one, two])
    assert len(rows) == 2
    assert duplicates == [{"extension": 19, "stand_number": "12", "property_ids": [1, 2]}]
    assert all("duplicate_extension_stand" in row["properties"]["qa_flags"] for row in rows)
