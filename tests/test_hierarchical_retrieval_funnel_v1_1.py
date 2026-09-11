from backend.retrieval_funnel import (
    Candidate,
    EvidenceState,
    FunnelInput,
    HierarchicalRetrievalFunnelV11,
    PoolObservation,
    Priority,
    SufficiencyTrigger,
)


def _request(reliable=True):
    return FunnelInput(1000, reliable, True)


def _candidate(candidate_id, area, **kwargs):
    return Candidate(candidate_id, area, **kwargs)


def _well_supported(candidate_id, area, pool=None):
    return _candidate(
        candidate_id,
        area,
        pool=pool or PoolObservation(observable=False),
        building=EvidenceState.MATCH,
        roof=EvidenceState.MATCH,
        house_pool=EvidenceState.MATCH,
        solar=EvidenceState.MATCH,
        driveway_garage=EvidenceState.MATCH,
        open_space=EvidenceState.MATCH,
        neighbour_context=EvidenceState.MATCH,
    )


def test_01_a_includes_plus_or_minus_five_percent_boundary():
    funnel = HierarchicalRetrievalFunnelV11()
    assert funnel.priority_for(_request(), _candidate("a", 1050)) == Priority.A


def test_02_b_is_greater_than_five_through_ten_percent():
    funnel = HierarchicalRetrievalFunnelV11()
    assert funnel.priority_for(_request(), _candidate("b", 1050.01)) == Priority.B
    assert funnel.priority_for(_request(), _candidate("b-edge", 1100)) == Priority.B


def test_03_c_is_greater_than_ten_through_twenty_percent():
    funnel = HierarchicalRetrievalFunnelV11()
    assert funnel.priority_for(_request(), _candidate("c", 1100.01)) == Priority.C
    assert funnel.priority_for(_request(), _candidate("c-edge", 1200)) == Priority.C


def test_04_d_is_greater_than_twenty_percent():
    assert HierarchicalRetrievalFunnelV11().priority_for(
        _request(), _candidate("d", 1200.01)
    ) == Priority.D


def test_05_pool_unknown_alone_never_expands():
    result = HierarchicalRetrievalFunnelV11().retrieve(
        _request(),
        [_well_supported(str(index), 1000) for index in range(3)]
        + [_candidate("b", 1075)],
    )
    assert all(stage.pool_unknown_count == stage.candidate_count for stage in result.stage_instrumentation)
    assert result.processed_candidate_ids == ("0", "1", "2")
    assert not result.expansions[0].expanded


def test_06_unknown_candidates_survive_as_recoverable():
    result = HierarchicalRetrievalFunnelV11().retrieve(
        _request(),
        [_well_supported(str(index), 1000) for index in range(3)]
        + [_candidate("unknown-b", 1075, pool=PoolObservation(observable=False))],
    )
    assert "unknown-b" in result.recoverable_candidate_ids


def test_07_a_is_processed_before_b_regardless_of_input_order():
    result = HierarchicalRetrievalFunnelV11().retrieve(
        _request(), [_candidate("b", 1075), _candidate("a", 1000)]
    )
    assert result.processed_candidate_ids[:2] == ("a", "b")


def test_08_b_expands_only_after_a_evidence_assessment():
    result = HierarchicalRetrievalFunnelV11().retrieve(
        _request(), [_candidate("a", 1000), _candidate("b", 1075)]
    )
    assert result.expansions[0].from_priority == Priority.A
    assert result.expansions[0].to_priority == Priority.B
    assert result.expansions[0].expanded
    assert SufficiencyTrigger.NO_ADEQUATE_CANDIDATES in result.expansions[0].triggers


def test_09_c_is_available_after_insufficient_ab_assessment():
    result = HierarchicalRetrievalFunnelV11().retrieve(
        _request(), [_candidate("a", 1000), _candidate("b", 1075), _candidate("c", 1150)]
    )
    assert result.expansions[1].from_priority == Priority.B
    assert result.expansions[1].to_priority == Priority.C
    assert "c" in result.processed_candidate_ids


def test_10_d_is_available_as_final_recovery():
    result = HierarchicalRetrievalFunnelV11().retrieve(
        _request(),
        [_candidate("a", 1000), _candidate("b", 1075), _candidate("c", 1150), _candidate("d", 1300)],
    )
    assert result.expansions[2].from_priority == Priority.C
    assert result.expansions[2].to_priority == Priority.D
    assert "d" in result.processed_candidate_ids


def test_11_area_cannot_dominate_final_compatibility():
    funnel = HierarchicalRetrievalFunnelV11()
    visual_match = funnel.base_funnel.assess(
        _request(),
        _candidate("visual", 1300, building=EvidenceState.MATCH, roof=EvidenceState.MATCH),
    )
    area_match_conflict = funnel.base_funnel.assess(
        _request(), _candidate("area", 1000, building=EvidenceState.CONFLICT)
    )
    assert visual_match.final_compatibility > area_match_conflict.final_compatibility


def test_12_w4_priority_counts_match_frozen_geometry_regression():
    candidates = (
        [_candidate(f"a-{index}", 1251) for index in range(270)]
        + [_candidate(f"b-{index}", 1314) for index in range(158)]
        + [_candidate(f"c-{index}", 1400) for index in range(468)]
        + [_candidate(f"d-{index}", 1600) for index in range(114)]
    )
    result = HierarchicalRetrievalFunnelV11().retrieve(FunnelInput(1251, True, True), candidates)
    assert result.priority_counts == {
        "A": 270,
        "B": 158,
        "C": 468,
        "D": 114,
        "NORMAL": 0,
        "universe": 1010,
    }


def test_13_w4_initial_expensive_workload_is_a_not_frozen_v1_queue():
    candidates = [_candidate(f"a-{index}", 1251) for index in range(270)] + [
        _candidate(f"b-{index}", 1314) for index in range(158)
    ]
    result = HierarchicalRetrievalFunnelV11().retrieve(FunnelInput(1251, True, True), candidates)
    assert result.immediate_expensive_workload == 270
    assert result.immediate_expensive_workload != 896


def test_14_unreliable_area_keeps_full_normal_recoverable_universe():
    result = HierarchicalRetrievalFunnelV11().retrieve(
        _request(reliable=False), [_candidate("a", 1000), _candidate("missing", None)]
    )
    assert result.priority_counts["NORMAL"] == 2
    assert result.processed_candidate_ids == ("a", "missing")
    assert result.recoverable_candidate_ids == ("a", "missing")
