"""Final user-facing candidate limit for PIE estate identification.

Internal passes may keep a large pool. The published result is Top 10 only.
Poor score separation must be reported; truncating is not a claim of certainty.
"""

from __future__ import annotations

FINAL_CANDIDATE_LIMIT = 10
INTERNAL_PASS2_SHORTLIST = 40

SUCCESS_STANDARD = {
    "top_1": "excellent",
    "top_3": "strong",
    "top_5": "useful",
    "top_10": "minimum acceptable identification",
    "outside_top_10": "benchmark failure requiring further improvement",
}

LOW_CONFIDENCE_MESSAGE = "LOW CONFIDENCE — candidates insufficiently separated."

# Gaps below these thresholds mean the Top 10 is a shortlist, not a unique ID.
MIN_TOP1_TOP2_GAP = 0.04
MIN_TOP1_TOP10_GAP = 0.10


def assess_separation(scores: list[float], *, limit: int = FINAL_CANDIDATE_LIMIT) -> dict:
    """Return confidence metadata for a frozen ranking. Does not change scores."""
    usable = [float(item) for item in scores[:limit] if item is not None]
    if len(usable) < 2:
        return {
            "level": "insufficient_candidates",
            "low_confidence": True,
            "message": LOW_CONFIDENCE_MESSAGE,
            "top1_to_top2_gap": None,
            "top1_to_top10_gap": None,
        }
    top1 = usable[0]
    top2 = usable[1]
    topn = usable[-1]
    gap_12 = round(top1 - top2, 4)
    gap_1n = round(top1 - topn, 4)
    low = gap_12 < MIN_TOP1_TOP2_GAP or gap_1n < MIN_TOP1_TOP10_GAP
    if not low and gap_12 >= 0.08 and gap_1n >= 0.15:
        level = "high"
    elif not low:
        level = "moderate"
    else:
        level = "low"
    return {
        "level": level,
        "low_confidence": low,
        "message": LOW_CONFIDENCE_MESSAGE if low else None,
        "top1_to_top2_gap": gap_12,
        "top1_to_top10_gap": gap_1n,
        "final_candidate_limit": limit,
    }


def freeze_final_candidates(ranked: list[dict], *, limit: int = FINAL_CANDIDATE_LIMIT) -> tuple[list[dict], dict]:
    """Slice a ranked list to the user-facing Top 10 and attach separation metadata."""
    final = [dict(row) for row in ranked[:limit]]
    for index, row in enumerate(final, start=1):
        row["rank"] = index
        row["strongest_positive_evidence"] = row.get("strongest_positive_evidence") or row.get("strongest_match")
        if "strongest_contradiction" not in row:
            row["strongest_contradiction"] = row.get("contradiction")
    scores = [row.get("total_score") for row in ranked]
    confidence = assess_separation(scores, limit=limit)
    if len(ranked) > limit:
        confidence["next_excluded_score"] = ranked[limit].get("total_score")
        confidence["next_excluded_stand"] = ranked[limit].get("stand_number")
    return final, confidence
