"""Listing Pool Gate v1 — inventory filter before detailed estate ranking.

Experimental. Does not modify production ranking, Scoring v2, Hybrid Pool
Geometry, viewpoint gates, or OS v1.

UNKNOWN inventory rows always survive. Missing inventory is treated as
UNKNOWN. Colour is not used.

Inventory NO is a removal signal for listing YES only when that NO is
observability-qualified. A raw detector miss is not a confident NO.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Mapping, Sequence

PoolStatus = Literal["YES", "NO", "UNKNOWN"]
VALID_STATUSES = frozenset({"YES", "NO", "UNKNOWN"})


def normalize_pool_status(value: Any) -> PoolStatus:
    status = str(value or "UNKNOWN").strip().upper()
    if status not in VALID_STATUSES:
        return "UNKNOWN"
    return status  # type: ignore[return-value]


def is_confident_pool_no(record: Mapping[str, Any] | None, status: Any | None = None) -> bool:
    """True only for a strengthened, observability-qualified inventory NO.

    Explicit candidate ``inventory_pool_status=NO`` without an inventory
    record keeps historic gate behaviour (tests and callers that already
    asserted NO). Versioned 1.1.0 inventory rows require
    ``pool_observability_adequate``. Inadequate-observability flags always
    demote NO to not-confident.
    """
    parcel = normalize_pool_status(
        status if status is not None else (None if record is None else record.get("pool_status"))
    )
    if parcel != "NO":
        return False
    flags = [str(item) for item in ((record or {}).get("diagnostic_flags") or (record or {}).get("flags") or [])]
    if "pool_observability_inadequate" in flags or "no_pool_candidate_insufficient_observability" in flags:
        return False
    algorithm = str((record or {}).get("algorithm_version") or "")
    if "1.1.0" in algorithm:
        return "pool_observability_adequate" in flags
    return True


def gate_pool_status(record: Mapping[str, Any] | None, explicit: Any | None = None) -> PoolStatus:
    if explicit in VALID_STATUSES:
        status = normalize_pool_status(explicit)
        if status != "NO":
            return status
        if record is None:
            return status
        return "NO" if is_confident_pool_no(record, status) else "UNKNOWN"
    if record is None:
        return "UNKNOWN"
    status = normalize_pool_status(record.get("pool_status"))
    if status != "NO":
        return status
    return "NO" if is_confident_pool_no(record, status) else "UNKNOWN"


def survives_listing_pool_gate(
    parcel_pool_status: Any,
    listing_pool_status: Any,
) -> bool:
    """Hard gate: discard only the opposite confident class.

    listing YES  → drop confident NO only
    listing NO   → drop confident YES only
    listing UNKNOWN → drop nothing
    parcel UNKNOWN → never dropped
    """
    listing = normalize_pool_status(listing_pool_status)
    parcel = normalize_pool_status(parcel_pool_status)
    if listing == "UNKNOWN":
        return True
    if parcel == "UNKNOWN":
        return True
    if listing == "YES":
        return parcel != "NO"
    return parcel != "YES"


@dataclass
class ListingPoolGateResult:
    listing_pool_status: PoolStatus
    starting_count: int
    survivors: list[dict[str, Any]] = field(default_factory=list)
    removed: list[dict[str, Any]] = field(default_factory=list)
    yes_survivors: int = 0
    no_survivors: int = 0
    unknown_survivors: int = 0
    removed_confident_no: int = 0
    removed_confident_yes: int = 0
    total_survivors: int = 0
    pct_reduction: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "listing_pool_status": self.listing_pool_status,
            "starting_count": self.starting_count,
            "parcels_removed_confident_no": self.removed_confident_no,
            "parcels_removed_confident_yes": self.removed_confident_yes,
            "yes_survivors": self.yes_survivors,
            "no_survivors": self.no_survivors,
            "unknown_survivors": self.unknown_survivors,
            "total_survivors": self.total_survivors,
            "pct_reduction": self.pct_reduction,
            "survivor_parcel_ids": [row.get("parcel_id") or row.get("stand_number") for row in self.survivors],
            "removed_parcel_ids": [row.get("parcel_id") or row.get("stand_number") for row in self.removed],
        }


def _inventory_index(
    records: Iterable[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for record in records:
        for key in ("parcel_id", "stand_number", "property_id"):
            value = record.get(key)
            if value is not None:
                index[str(value)] = record
                index[str(value).replace("/", "_")] = record
        stand = record.get("stand_number")
        if stand is not None:
            index[str(stand).replace("/", "_")] = record
    return index


def _lookup(candidate: Mapping[str, Any], index: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any] | None:
    for key in ("parcel_id", "property_id", "stand_number"):
        value = candidate.get(key)
        if value is None:
            continue
        found = index.get(str(value)) or index.get(str(value).replace("/", "_"))
        if found:
            return found
    return None


def apply_listing_pool_gate(
    candidates: Sequence[Mapping[str, Any]],
    inventory_records: Iterable[Mapping[str, Any]],
    listing_pool_status: Any,
) -> ListingPoolGateResult:
    """Filter candidates before detailed ranking. Does not score."""
    listing = normalize_pool_status(listing_pool_status)
    index = _inventory_index(inventory_records)
    survivors: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    yes = no = unknown = 0
    removed_no = removed_yes = 0

    for raw in candidates:
        candidate = dict(raw)
        record = _lookup(candidate, index)
        explicit = candidate.get("inventory_pool_status")
        source_record: Mapping[str, Any] | None
        if explicit in VALID_STATUSES:
            parcel_status = gate_pool_status(record, explicit)
            reason = candidate.get("unknown_reason")
            source_record = record
        elif record is not None:
            parcel_status = gate_pool_status(record)
            reason = record.get("unknown_reason")
            source_record = record
        elif candidate.get("pool_status") in VALID_STATUSES:
            parcel_status = gate_pool_status(candidate, candidate.get("pool_status"))
            reason = candidate.get("unknown_reason")
            source_record = candidate
        else:
            parcel_status = "UNKNOWN"
            reason = "missing_inventory_record"
            source_record = None
        if (
            parcel_status == "UNKNOWN"
            and source_record is not None
            and normalize_pool_status(source_record.get("pool_status")) == "NO"
            and not is_confident_pool_no(source_record)
        ):
            reason = source_record.get("unknown_reason") or "pool_no_not_observability_qualified"
        candidate["inventory_pool_status"] = parcel_status
        candidate["inventory_unknown_reason"] = reason

        if survives_listing_pool_gate(parcel_status, listing):
            survivors.append(candidate)
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
    return ListingPoolGateResult(
        listing_pool_status=listing,
        starting_count=starting,
        survivors=survivors,
        removed=removed,
        yes_survivors=yes,
        no_survivors=no,
        unknown_survivors=unknown,
        removed_confident_no=removed_no,
        removed_confident_yes=removed_yes,
        total_survivors=total,
        pct_reduction=0.0 if starting == 0 else round(100.0 * (starting - total) / starting, 2),
    )


def filter_before_ranking(
    candidates: Sequence[Mapping[str, Any]],
    inventory_records: Iterable[Mapping[str, Any]],
    listing_pool_status: Any,
) -> list[dict[str, Any]]:
    """Public pre-rank hook. Production ranking is not wired to this yet."""
    return apply_listing_pool_gate(candidates, inventory_records, listing_pool_status).survivors
