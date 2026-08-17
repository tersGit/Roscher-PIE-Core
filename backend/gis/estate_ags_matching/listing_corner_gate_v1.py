"""Corner Gate v1 — contextual candidate filter after Pool Gate.

Does not modify Scoring v2 weights, Pool Gate, Hybrid, OS v1, or inventory.
UNKNOWN is always retained. The primary v1 action is high-confidence listing
YES removing confident parcel NO.

Pipeline order:
  listing acquisition → Pool Gate → Corner Gate → Hybrid / Scoring v2 ranking
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Mapping, Sequence

from backend.gis.estate_ags_matching.listing_corner_evidence_v1 import (
    EXCEPTIONAL_NO_CONFIDENCE,
    HIGH_YES_CONFIDENCE,
    ListingCornerEvidence,
    normalize_corner_status,
)
from backend.gis.estate_ags_matching.parcel_corner_v1 import index_corner_records

CornerStatus = Literal["YES", "NO", "UNKNOWN"]
VALID = frozenset({"YES", "NO", "UNKNOWN"})


def survives_listing_corner_gate(
    parcel_corner: Any,
    listing_corner: Any,
    *,
    listing_confidence: float = 0.0,
    listing_high_confidence: bool | None = None,
    listing_exceptional_non_corner: bool | None = None,
    positive_non_corner_evidence: bool = False,
) -> tuple[bool, str | None]:
    """Hard gate. Returns (survives, unresolved_reason)."""
    listing = normalize_corner_status(listing_corner)
    parcel = normalize_corner_status(parcel_corner)
    high = listing_high_confidence
    if high is None:
        high = listing == "YES" and float(listing_confidence) >= HIGH_YES_CONFIDENCE
    exceptional = listing_exceptional_non_corner
    if exceptional is None:
        exceptional = (
            listing == "NO"
            and float(listing_confidence) >= EXCEPTIONAL_NO_CONFIDENCE
            and bool(positive_non_corner_evidence)
        )

    if listing == "UNKNOWN":
        return True, None
    if listing == "YES" and high:
        if parcel == "NO":
            return False, None
        if parcel == "UNKNOWN":
            return True, "unresolved_parcel_corner"
        return True, None
    if listing == "YES":
        # Medium listing YES is not a removal signal in v1.
        return True, "listing_corner_yes_below_high_confidence_neutral"
    if listing == "NO" and exceptional:
        if parcel == "YES":
            return False, None
        if parcel == "UNKNOWN":
            return True, "unresolved_parcel_corner"
        return True, None
    return True, "listing_corner_no_treated_as_neutral_v1"


@dataclass
class ListingCornerGateResult:
    listing_corner: CornerStatus
    listing_confidence: float
    listing_high_confidence: bool
    starting_count: int
    survivors: list[dict[str, Any]] = field(default_factory=list)
    removed: list[dict[str, Any]] = field(default_factory=list)
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    yes_survivors: int = 0
    no_survivors: int = 0
    unknown_survivors: int = 0
    removed_confident_no: int = 0
    removed_confident_yes: int = 0
    total_survivors: int = 0
    pct_reduction: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "listing_corner": self.listing_corner,
            "listing_confidence": self.listing_confidence,
            "listing_high_confidence": self.listing_high_confidence,
            "starting_count": self.starting_count,
            "parcels_removed_confident_no": self.removed_confident_no,
            "parcels_removed_confident_yes": self.removed_confident_yes,
            "yes_survivors": self.yes_survivors,
            "no_survivors": self.no_survivors,
            "unknown_survivors": self.unknown_survivors,
            "unresolved_count": len(self.unresolved),
            "total_survivors": self.total_survivors,
            "pct_reduction": self.pct_reduction,
            "survivor_parcel_ids": [row.get("parcel_id") or row.get("stand_number") for row in self.survivors],
            "removed_parcel_ids": [row.get("parcel_id") or row.get("stand_number") for row in self.removed],
            "unresolved_parcel_ids": [row.get("parcel_id") or row.get("stand_number") for row in self.unresolved],
        }


def _lookup(candidate: Mapping[str, Any], index: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any] | None:
    for key in ("parcel_id", "property_id", "stand_number"):
        value = candidate.get(key)
        if value is None:
            continue
        found = index.get(str(value)) or index.get(str(value).replace("/", "_"))
        if found:
            return found
    return None


def apply_listing_corner_gate(
    candidates: Sequence[Mapping[str, Any]],
    parcel_corner_records: Iterable[Mapping[str, Any]],
    listing_corner: Any,
    *,
    listing_confidence: float = 0.0,
    listing_high_confidence: bool | None = None,
    listing_exceptional_non_corner: bool | None = None,
    positive_non_corner_evidence: bool = False,
    listing_evidence: ListingCornerEvidence | Mapping[str, Any] | None = None,
) -> ListingCornerGateResult:
    """Filter Pool Gate survivors. Does not score and does not change Pool Gate."""
    if listing_evidence is not None:
        payload = listing_evidence.to_dict() if isinstance(listing_evidence, ListingCornerEvidence) else dict(listing_evidence)
        listing_corner = payload.get("listing_corner") or payload.get("classification") or listing_corner
        listing_confidence = float(payload.get("confidence") or listing_confidence)
        listing_high_confidence = bool(payload.get("high_confidence")) if listing_high_confidence is None else listing_high_confidence
        listing_exceptional_non_corner = (
            bool(payload.get("exceptional_non_corner"))
            if listing_exceptional_non_corner is None
            else listing_exceptional_non_corner
        )
        positive_non_corner_evidence = bool(payload.get("positive_non_corner_evidence") or positive_non_corner_evidence)

    listing = normalize_corner_status(listing_corner)
    high = listing_high_confidence
    if high is None:
        high = listing == "YES" and float(listing_confidence) >= HIGH_YES_CONFIDENCE
    index = index_corner_records(parcel_corner_records)
    survivors: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    yes = no = unknown = 0
    removed_no = removed_yes = 0

    for raw in candidates:
        candidate = dict(raw)
        record = _lookup(candidate, index)
        explicit = candidate.get("parcel_corner") or candidate.get("gis_corner")
        if explicit in VALID:
            parcel_status = normalize_corner_status(explicit)
            reason = candidate.get("parcel_corner_reason")
            conf = candidate.get("parcel_corner_confidence")
        elif record is not None:
            parcel_status = normalize_corner_status(record.get("classification"))
            reason = record.get("reason")
            conf = record.get("confidence")
        else:
            parcel_status = "UNKNOWN"
            reason = "missing_parcel_corner_record"
            conf = 0.0
        candidate["parcel_corner"] = parcel_status
        candidate["parcel_corner_reason"] = reason
        candidate["parcel_corner_confidence"] = conf
        keep, unresolved_reason = survives_listing_corner_gate(
            parcel_status,
            listing,
            listing_confidence=listing_confidence,
            listing_high_confidence=high,
            listing_exceptional_non_corner=listing_exceptional_non_corner,
            positive_non_corner_evidence=positive_non_corner_evidence,
        )
        candidate["corner_gate_unresolved"] = unresolved_reason
        if keep:
            survivors.append(candidate)
            if unresolved_reason == "unresolved_parcel_corner":
                unresolved.append(candidate)
            if parcel_status == "YES":
                yes += 1
            elif parcel_status == "NO":
                no += 1
            else:
                unknown += 1
        else:
            removed.append(candidate)
            if parcel_status == "NO":
                removed_no += 1
            elif parcel_status == "YES":
                removed_yes += 1

    starting = len(candidates)
    total = len(survivors)
    return ListingCornerGateResult(
        listing_corner=listing,
        listing_confidence=round(float(listing_confidence), 4),
        listing_high_confidence=bool(high),
        starting_count=starting,
        survivors=survivors,
        removed=removed,
        unresolved=unresolved,
        yes_survivors=yes,
        no_survivors=no,
        unknown_survivors=unknown,
        removed_confident_no=removed_no,
        removed_confident_yes=removed_yes,
        total_survivors=total,
        pct_reduction=0.0 if starting == 0 else round(100.0 * (starting - total) / starting, 2),
    )


def apply_pool_then_corner_gate(
    candidates: Sequence[Mapping[str, Any]],
    inventory_records: Iterable[Mapping[str, Any]],
    listing_pool_status: Any,
    parcel_corner_records: Iterable[Mapping[str, Any]],
    listing_corner: Any,
    **corner_kwargs: Any,
) -> tuple[Any, ListingCornerGateResult]:
    """Acquisition-agnostic pre-rank gates. Does not alter Pool Gate internals."""
    from backend.gis.estate_ags_matching.listing_pool_gate_v1 import apply_listing_pool_gate

    pool = apply_listing_pool_gate(candidates, inventory_records, listing_pool_status)
    corner = apply_listing_corner_gate(pool.survivors, parcel_corner_records, listing_corner, **corner_kwargs)
    return pool, corner
