from backend.retrieval_funnel.hierarchical_v1_3 import (
    AreaConfidence, AreaQualifier, HighConfidenceStandSizeGate, ListingAreaAssessment,
    ListingAreaClassifier, ListingAreaFact, ListingAreaSource, RescueTrigger,
    StandSizeCandidate, StandSizePriority,
)


def _high(area=1000):
    return ListingAreaAssessment(area, AreaConfidence.HIGH_CONFIDENCE, "test")


def _candidate(candidate_id, area):
    return StandSizeCandidate(candidate_id, area)


def test_01_high_confidence_enables_gate():
    result = HighConfidenceStandSizeGate().select(_high(), [_candidate("a", 1000)])
    payload = result.instrumentation()
    assert result.gate_enabled
    assert payload["listing_area_confidence"] == "HIGH_CONFIDENCE"
    assert payload["plus_minus_10_lower_m2"] == 900
    assert payload["plus_minus_10_upper_m2"] == 1100
    assert payload["normal_count"] == 1 and not payload["rescue_activated"]


def test_02_within_five_percent_is_priority_a():
    assert HighConfidenceStandSizeGate().select(_high(), [_candidate("a", 1050)]).priority_a_ids == ("a",)


def test_03_over_five_through_ten_percent_is_priority_b():
    assert HighConfidenceStandSizeGate().select(_high(), [_candidate("b", 1095)]).priority_b_ids == ("b",)


def test_04_over_ten_percent_is_excluded_from_ordinary_queue():
    gate = HighConfidenceStandSizeGate()
    result = gate.select(_high(), [
        _candidate("plus-eight", 1080), _candidate("minus-nine-point-five", 905),
        _candidate("plus-ten-point-one", 1101), _candidate("plus-fourteen", 1140),
        _candidate("plus-twenty-five", 1250),
    ])
    assert result.normal_candidate_ids == ("plus-eight", "minus-nine-point-five")
    assert result.excluded_from_ordinary_queue_ids == (
        "plus-ten-point-one", "plus-fourteen", "plus-twenty-five"
    )
    assert result.rescue_c_ids == ("plus-ten-point-one", "plus-fourteen")
    assert result.rescue_d_ids == ("plus-twenty-five",)


def test_05_over_ten_percent_is_available_to_exceptional_rescue():
    result = HighConfidenceStandSizeGate().select(_high(), [_candidate("c", 1101)])
    assert result.exceptional_rescue_ids == ("c",)


def test_06_visual_unknown_is_not_a_rescue_trigger():
    result = HighConfidenceStandSizeGate().select(_high(), [_candidate("c", 1140)])
    assert not HighConfidenceStandSizeGate().activate_rescue(result, ()).activated
    try:
        HighConfidenceStandSizeGate().activate_rescue(result, ("HIGH_UNKNOWN_VISUAL_RATE",))
    except ValueError:
        pass
    else:
        raise AssertionError("High unknown visual rate must not activate rescue.")


def test_07_conflicting_listing_figures_disable_gate():
    assessment = ListingAreaClassifier().classify([
        ListingAreaFact(1000, ListingAreaSource.ERF_SIZE),
        ListingAreaFact(1200, ListingAreaSource.LAND_SIZE),
    ])
    assert assessment.confidence == AreaConfidence.MEDIUM
    assert not HighConfidenceStandSizeGate().select(assessment, [_candidate("a", 1000)]).gate_enabled


def test_08_approximate_listing_area_disables_gate():
    assessment = ListingAreaClassifier().classify([
        ListingAreaFact(1000, ListingAreaSource.ERF_SIZE, AreaQualifier.APPROXIMATE)
    ])
    assert assessment.confidence == AreaConfidence.LOW
    assert not HighConfidenceStandSizeGate().select(assessment, [_candidate("a", 1000)]).gate_enabled
    uncertain = ListingAreaAssessment(1000, AreaConfidence.UNKNOWN, "missing")
    assert not HighConfidenceStandSizeGate().select(uncertain, [_candidate("any", 1250)]).gate_enabled


def test_09_rescue_c_activates_only_after_eligible_failure():
    result = HighConfidenceStandSizeGate().select(_high(), [_candidate("c", 1140)])
    rescue = HighConfidenceStandSizeGate().activate_rescue(
        result, (RescueTrigger.NO_CREDIBLE_CANDIDATES,)
    )
    assert rescue.levels == (StandSizePriority.C,)


def test_10_rescue_d_activates_only_after_c_failure():
    result = HighConfidenceStandSizeGate().select(_high(), [_candidate("c", 1140), _candidate("d", 1250)])
    rescue = HighConfidenceStandSizeGate().activate_rescue(
        result, (RescueTrigger.NO_CREDIBLE_CANDIDATES,), c_failed_eligible_criterion=True
    )
    assert rescue.levels == (StandSizePriority.C, StandSizePriority.D)


def test_11_production_scoring_module_is_not_mutated():
    import backend.retrieval_funnel.funnel as production
    assert HighConfidenceStandSizeGate.__module__ != production.__name__


def test_12_evidence_and_recovery_semantics_remain_isolated():
    import backend.retrieval_funnel.hierarchical_v1_2 as v12
    assert not hasattr(v12, "HighConfidenceStandSizeGate")
