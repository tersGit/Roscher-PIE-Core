from backend.gis.estate_ags_matching.final_candidates import (
    FINAL_CANDIDATE_LIMIT,
    LOW_CONFIDENCE_MESSAGE,
    assess_separation,
    freeze_final_candidates,
)


def test_final_limit_is_ten():
    assert FINAL_CANDIDATE_LIMIT == 10


def test_freeze_returns_only_ten():
    ranked = [{"stand_number": str(i), "total_score": 1.0 - i * 0.01} for i in range(1, 21)]
    final, confidence = freeze_final_candidates(ranked)
    assert len(final) == 10
    assert [row["rank"] for row in final] == list(range(1, 11))
    assert final[-1]["stand_number"] == "10"
    assert confidence["next_excluded_stand"] == "11"


def test_close_scores_are_low_confidence():
    scores = [0.757, 0.749, 0.749, 0.730, 0.706, 0.703, 0.698, 0.697, 0.689, 0.684]
    result = assess_separation(scores)
    assert result["low_confidence"] is True
    assert result["message"] == LOW_CONFIDENCE_MESSAGE
    assert result["level"] == "low"


def test_separated_scores_are_not_low_confidence():
    scores = [0.92, 0.71, 0.64, 0.58, 0.51, 0.44, 0.40, 0.36, 0.33, 0.30]
    result = assess_separation(scores)
    assert result["low_confidence"] is False
    assert result["level"] == "high"
