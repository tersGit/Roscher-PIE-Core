import numpy as np

from backend.gis.estate_ags_matching.parcel_bound_geometry_v1 import (
    Binding, Observability, Quality, SourceMetadata, WaterCount, assess_binding,
    build_record, geometry_candidate_ids, lane_evidence, measure_object,
)
from backend.retrieval_funnel.hierarchical_v1_3 import (
    AreaConfidence, HighConfidenceStandSizeGate, ListingAreaAssessment, RescueTrigger, StandSizeCandidate,
)


def masks():
    parcel = np.zeros((100, 100), bool); parcel[10:90, 10:90] = True
    pool = np.zeros_like(parcel); pool[40:50, 20:40] = True
    building = np.zeros_like(parcel); building[60:80, 50:80] = True
    return parcel, pool, building


def gate():
    return HighConfidenceStandSizeGate().select(ListingAreaAssessment(1000, AreaConfidence.HIGH_CONFIDENCE, "test"), [StandSizeCandidate("a", 1000), StandSizeCandidate("c", 1140)])


def test_01_rescue_over_ten_has_no_normal_geometry():
    assert geometry_candidate_ids(gate()) == ("a",)

def test_02_legitimate_rescue_enables_geometry():
    rescue = HighConfidenceStandSizeGate().activate_rescue(gate(), [RescueTrigger.NO_CREDIBLE_CANDIDATES])
    assert geometry_candidate_ids(gate(), rescue) == ("a", "c")

def test_03_outside_object_never_binds():
    parcel, pool, _ = masks(); pool[:] = False; pool[0:5, 0:5] = True
    assert assess_binding(pool, parcel).binding == Binding.OUTSIDE_PARCEL

def test_04_crossing_centroid_is_insufficient():
    parcel, pool, _ = masks(); pool[:] = False; pool[40:50, 5:45] = True
    assert assess_binding(pool, parcel).binding == Binding.AMBIGUOUS

def test_05_valid_pool_geometry():
    parcel, pool, _ = masks()
    assert measure_object(pool, parcel, observability=Observability.OBSERVED).quality == Quality.HIGH

def test_06_pool_aspect():
    parcel, pool, _ = masks()
    assert measure_object(pool, parcel).aspect_ratio == 2.1111

def test_07_pool_orientation():
    parcel, pool, _ = masks()
    assert measure_object(pool, parcel).major_orientation_deg == 0

def test_08_pool_parcel_normalization():
    parcel, pool, _ = masks()
    assert measure_object(pool, parcel).centroid_normalized_parcel == (0.2468, 0.4367)

def test_09_multiple_water():
    parcel, pool, _ = masks(); other = np.zeros_like(parcel); other[20:25, 50:55] = True
    assert build_record(SourceMetadata("x"), parcel, [pool, other]).multiple_water.count == WaterCount.TWO_OR_MORE

def test_10_building_geometry():
    parcel, _, building = masks()
    assert build_record(SourceMetadata("x"), parcel, building_mask=building).building.area_px is not None

def test_11_building_parcel_normalization():
    parcel, _, building = masks()
    assert build_record(SourceMetadata("x"), parcel, building_mask=building).building.centroid_normalized_parcel == (0.6899, 0.7532)

def test_12_relation_geometry():
    parcel, pool, building = masks()
    assert build_record(SourceMetadata("x"), parcel, [pool], building).relation.quality == Quality.HIGH

def test_13_low_quality_cannot_enter_discriminating_lane():
    parcel, pool, _ = masks(); pool[:] = False; pool[0:5, 0:5] = True
    record = build_record(SourceMetadata("x"), parcel, [pool])
    assert not lane_evidence(record, [record]).observable

def test_14_unknown_is_recoverable():
    parcel, _, _ = masks()
    assert not lane_evidence(build_record(SourceMetadata("x"), parcel), []).observable

def test_15_target_compatible_schema():
    assert "metadata" in build_record(SourceMetadata("x"), *masks()[:1]).to_dict()

def test_16_distinctiveness_is_population_rarity():
    parcel, pool, _ = masks()
    record = build_record(SourceMetadata("x"), parcel, [pool])
    assert lane_evidence(record, [record]).distinctive_components == 1

def test_17_v13_gate_is_unchanged():
    assert gate().normal_candidate_ids == ("a",)

def test_18_production_is_unchanged():
    import backend.retrieval_funnel.funnel as production
    assert not hasattr(production, "ParcelBoundGeometryRecord")
