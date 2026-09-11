from backend.retrieval_funnel.hierarchical_v1_2 import (
    Compatibility, ExpansionTrigger, HierarchicalRetrievalFunnelV12, Lane,
    LaneCandidate, ObservableEvidence,
)


def _strong(distinctive=1):
    return ObservableEvidence(True, True, Compatibility.STRONG_MATCH, distinctive)


def _candidate(candidate_id, pool=ObservableEvidence(), building=ObservableEvidence()):
    return LaneCandidate(candidate_id, "A", pool, building)


def test_01_observed_discriminating_evidence_enters_evidence_lane():
    assert HierarchicalRetrievalFunnelV12().process_band("A", [_candidate("a", _strong())]).evidence_candidate_ids == ("a",)


def test_02_unknown_enters_recovery_lane():
    assert HierarchicalRetrievalFunnelV12().process_band("A", [_candidate("a")]).recovery_candidate_ids == ("a",)


def test_03_recovery_candidate_is_never_eliminated():
    result = HierarchicalRetrievalFunnelV12().process_band("A", [_candidate("a")])
    assert result.assessments[0].recoverable


def test_04_strong_building_promotes_recovery_candidate():
    result = HierarchicalRetrievalFunnelV12().process_band("A", [_candidate("a", building=_strong())])
    assert result.promotion_ids == ("a",)


def test_05_visible_building_conflict_demotes_evidence_candidate():
    conflict = ObservableEvidence(True, True, Compatibility.VISIBLE_CONFLICT)
    result = HierarchicalRetrievalFunnelV12().process_band("A", [_candidate("a", _strong(), conflict)])
    assert result.demotion_ids == ("a",) and result.recovery_candidate_ids == ("a",)


def test_06_generic_observability_is_not_strong_evidence():
    observed = ObservableEvidence(True, True, Compatibility.MATCH)
    assert HierarchicalRetrievalFunnelV12().process_band("A", [_candidate("a", observed)]).evidence_candidate_ids == ()


def test_07_distinctiveness_orders_evidence_priority():
    result = HierarchicalRetrievalFunnelV12().process_band("A", [_candidate("common", _strong(1)), _candidate("rare", _strong(3))])
    assert result.expensive_candidate_ids == ("rare", "common")


def test_08_high_unknown_count_does_not_trigger_expansion():
    result = HierarchicalRetrievalFunnelV12().process_band("A", [_candidate(str(i), _strong()) for i in range(5)] + [_candidate("unknown") for _ in range(50)])
    assert ExpansionTrigger.NO_STRONG_EVIDENCE_LANE not in result.triggers


def test_09_credible_small_evidence_lane_stops_expansion():
    result = HierarchicalRetrievalFunnelV12().process_band("A", [_candidate(str(i), _strong()) for i in range(5)])
    assert result.stopped


def test_10_recovery_remains_available_after_stop():
    result = HierarchicalRetrievalFunnelV12().process_band("A", [_candidate(str(i), _strong()) for i in range(5)] + [_candidate("later")])
    assert result.stopped and "later" in result.recovery_candidate_ids


def test_11_later_area_bands_are_recoverable():
    result = HierarchicalRetrievalFunnelV12().process_band("B", [_candidate("b")])
    assert result.area_band == "B" and result.recovery_candidate_ids == ("b",)


def test_12_production_ranking_is_not_imported_or_mutated():
    import backend.retrieval_funnel.hierarchical_v1_2 as experimental
    assert not hasattr(experimental, "RetrievalFunnel")
