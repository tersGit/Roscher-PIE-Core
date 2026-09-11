from backend.retrieval_funnel import (
    Candidate,
    EvidenceState,
    FunnelInput,
    PoolObservation,
    PoolState,
    RetrievalFunnel,
    Tier,
)


def _candidate(candidate_id, area, **kwargs):
    return Candidate(candidate_id, area, **kwargs)


def _request(pool=True, reliable=True):
    return FunnelInput(1000, reliable, pool)


def test_tier_boundaries_are_inclusive_and_retained():
    funnel = RetrievalFunnel()
    low = funnel.assess(_request(), _candidate("low", 900))
    t1 = funnel.assess(_request(), _candidate("t1", 1100))
    t2 = funnel.assess(_request(), _candidate("t2", 1200))
    t3 = funnel.assess(_request(), _candidate("t3", 1201))
    assert [low.tier, t1.tier, t2.tier, t3.tier] == [Tier.T1, Tier.T1, Tier.T2, Tier.T3]
    assert t2.absolute_area_difference_m2 == 200
    assert t2.percent_area_difference == 0.2


def test_missing_or_unreliable_listing_size_starts_full_normal_universe():
    funnel = RetrievalFunnel()
    result = funnel.retrieve(_request(reliable=False), [_candidate("a", 1000), _candidate("b", None)])
    assert result.expensive_queue == ("a", "b")
    assert {item.tier for item in result.assessments} == {Tier.NORMAL}


def test_unknown_pool_is_preserved_and_missing_detector_is_not_no_pool():
    state = PoolObservation(observable=True, pool_detected=False, clear_absence=False).state()
    result = RetrievalFunnel().retrieve(_request(), [_candidate("a", 1000, pool=PoolObservation(observable=False))])
    assert state == PoolState.UNKNOWN
    assert result.assessments[0].pool_state == PoolState.UNKNOWN
    assert result.expensive_queue == ("a",)


def test_visible_pool_absence_is_deprioritized_when_listing_has_pool():
    funnel = RetrievalFunnel()
    no_pool = funnel.assess(_request(), _candidate("no", 1000, pool=PoolObservation(observable=True, clear_absence=True)))
    pool = funnel.assess(_request(), _candidate("yes", 1000, pool=PoolObservation(observable=True, pool_detected=True, parcel_bound=True)))
    assert no_pool.pool_priority < 0 < pool.pool_priority


def test_pool_expectation_is_reversed_for_listing_without_pool():
    funnel = RetrievalFunnel()
    absent = funnel.assess(_request(pool=False), _candidate("no", 1000, pool=PoolObservation(observable=True, clear_absence=True)))
    present = funnel.assess(_request(pool=False), _candidate("yes", 1000, pool=PoolObservation(observable=True, pool_detected=True, parcel_bound=True)))
    assert absent.pool_priority > 0 > present.pool_priority


def test_tier2_expands_for_insufficient_tier1_support():
    result = RetrievalFunnel().retrieve(_request(), [_candidate("t1", 1000), _candidate("t2", 1150)])
    assert "insufficient_tier1_support" in result.expansion_reasons
    assert result.expensive_queue == ("t1", "t2")


def test_high_unknown_observability_expands_tier2():
    candidates = [_candidate(f"t1-{n}", 1000, pool=PoolObservation(observable=False)) for n in range(3)]
    result = RetrievalFunnel().retrieve(_request(), candidates + [_candidate("t2", 1150)])
    assert "high_unknown_pool_observability" in result.expansion_reasons
    assert "t2" in result.expensive_queue


def test_tier3_is_always_recoverable_not_eliminated():
    funnel = RetrievalFunnel()
    result = funnel.retrieve(_request(), [_candidate("t1a", 1000), _candidate("t1b", 1001), _candidate("t1c", 1002), _candidate("t3", 1300)])
    assert "t3" not in result.expensive_queue
    assert result.recoverable_tier3 == ("t3",)
    assert funnel.recover_tier3(result) == ("t3",)


def test_unknown_evidence_never_creates_conflict_penalty():
    funnel = RetrievalFunnel()
    unknown = funnel.assess(_request(), _candidate("unknown", 1300))
    conflict = funnel.assess(_request(), _candidate("conflict", 1300, building=EvidenceState.CONFLICT))
    assert unknown.final_compatibility > conflict.final_compatibility


def test_stand_size_has_strictly_weak_final_contribution_and_cannot_dominate():
    funnel = RetrievalFunnel()
    assessment = funnel.assess(_request(), _candidate("t1", 1000))
    visual_match = funnel.assess(
        _request(),
        _candidate(
            "visual-match",
            1300,
            building=EvidenceState.MATCH,
            roof=EvidenceState.MATCH,
            house_pool=EvidenceState.MATCH,
        ),
    )
    size_match_with_conflict = funnel.assess(
        _request(),
        _candidate("size-match", 1000, building=EvidenceState.CONFLICT),
    )
    assert assessment.stand_size_final_contribution == 0.05
    assert assessment.stand_size_final_contribution < 0.1
    assert visual_match.final_compatibility > size_match_with_conflict.final_compatibility


def test_external_neighbour_pool_is_unknown_not_parcel_pool_and_cannot_enable_geometry():
    funnel = RetrievalFunnel()
    external = _candidate(
        "external",
        1000,
        pool=PoolObservation(observable=True, pool_detected=True, parcel_bound=False, reason="neighbour_pool"),
        pool_geometry=EvidenceState.CONFLICT,
    )
    neutral = _candidate("neutral", 1000)
    state = external.pool.state()
    assert state == PoolState.UNKNOWN
    assert funnel.assess(_request(), external).final_compatibility == funnel.assess(_request(), neutral).final_compatibility


def test_low_observation_coverage_triggers_fallback_and_instruments_savings():
    result = RetrievalFunnel().retrieve(
        _request(pool=None),
        [_candidate("a", 1000), _candidate("b", 1001), _candidate("c", 1002), _candidate("t2", 1150), _candidate("t3", 1300)],
    )
    assert "low_evidence_coverage" in result.expansion_reasons
    assert result.stage_counts["universe"] == 5
    assert result.estimated_expensive_work_reduction == 0.2
