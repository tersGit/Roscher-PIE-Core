"""Evidence-led retrieval ordering for the PIE experimental funnel V1.

The funnel orders work; it neither identifies a property nor replaces frozen
Scoring v2.  Observation state and compatibility state remain deliberately
separate so missing imagery or a missing detector result cannot become a
negative match claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, Sequence


class Tier(str, Enum):
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    NORMAL = "NORMAL"


class PoolState(str, Enum):
    OBSERVED_POOL = "OBSERVED_POOL"
    OBSERVED_NO_POOL = "OBSERVED_NO_POOL"
    UNKNOWN = "UNKNOWN"


class EvidenceState(str, Enum):
    MATCH = "MATCH"
    PARTIAL = "PARTIAL"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class PoolObservation:
    """Candidate-side observation, requiring a pool detection to be parcel bound."""

    observable: bool = False
    pool_detected: bool = False
    parcel_bound: bool = False
    clear_absence: bool = False
    reason: str = "not_visible"

    def state(self) -> PoolState:
        if not self.observable:
            return PoolState.UNKNOWN
        if self.pool_detected:
            return PoolState.OBSERVED_POOL if self.parcel_bound else PoolState.UNKNOWN
        if self.clear_absence:
            return PoolState.OBSERVED_NO_POOL
        return PoolState.UNKNOWN


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    cadastral_area_m2: float | None
    pool: PoolObservation = field(default_factory=PoolObservation)
    building: EvidenceState = EvidenceState.UNKNOWN
    roof: EvidenceState = EvidenceState.UNKNOWN
    house_pool: EvidenceState = EvidenceState.UNKNOWN
    pool_geometry: EvidenceState = EvidenceState.UNKNOWN
    solar: EvidenceState = EvidenceState.UNKNOWN
    driveway_garage: EvidenceState = EvidenceState.UNKNOWN
    open_space: EvidenceState = EvidenceState.UNKNOWN
    neighbour_context: EvidenceState = EvidenceState.UNKNOWN


@dataclass(frozen=True)
class FunnelInput:
    listing_area_m2: float | None
    listing_area_reliable: bool
    listing_has_pool: bool | None


@dataclass(frozen=True)
class FunnelConfig:
    minimum_tier1_support: int = 3
    unknown_pool_fraction_for_fallback: float = 0.5
    low_confidence_coverage: float = 0.35
    stand_size_final_weight: float = 0.05


@dataclass(frozen=True)
class CandidateAssessment:
    candidate: Candidate
    tier: Tier
    absolute_area_difference_m2: float | None
    percent_area_difference: float | None
    pool_state: PoolState
    pool_priority: float
    evidence_coverage: float
    final_compatibility: float
    stand_size_final_contribution: float


@dataclass(frozen=True)
class FunnelResult:
    assessments: tuple[CandidateAssessment, ...]
    expensive_queue: tuple[str, ...]
    recoverable_tier3: tuple[str, ...]
    expansion_reasons: tuple[str, ...]
    stage_counts: dict[str, int]
    estimated_expensive_work_reduction: float


class VLMReranker(Protocol):
    """Optional adapter for applying a VLM only to the expensive queue."""

    def rerank(self, candidate_ids: Sequence[str]) -> Sequence[str]: ...


_STATE_SCORE = {
    EvidenceState.MATCH: 1.0,
    EvidenceState.PARTIAL: 0.5,
    EvidenceState.CONFLICT: -1.0,
    EvidenceState.UNKNOWN: 0.0,
}
_SECONDARY_FIELDS = (
    "building",
    "roof",
    "house_pool",
    "solar",
    "driveway_garage",
    "open_space",
    "neighbour_context",
)


class RetrievalFunnel:
    """Build a recoverable, progressively-expensive candidate work queue."""

    def __init__(self, config: FunnelConfig = FunnelConfig()) -> None:
        if not 0.0 < config.stand_size_final_weight < 0.1:
            raise ValueError("stand_size_final_weight must remain weak (< 0.1)")
        self.config = config

    def assess(self, request: FunnelInput, candidate: Candidate) -> CandidateAssessment:
        absolute, percent, tier = self._area_metrics(request, candidate.cadastral_area_m2)
        pool_state = candidate.pool.state()
        pool_priority = self._pool_priority(request.listing_has_pool, pool_state)
        coverage = self._coverage(candidate)
        final, area_contribution = self._final_compatibility(
            request, tier, candidate, pool_state
        )
        return CandidateAssessment(
            candidate=candidate,
            tier=tier,
            absolute_area_difference_m2=absolute,
            percent_area_difference=percent,
            pool_state=pool_state,
            pool_priority=pool_priority,
            evidence_coverage=coverage,
            final_compatibility=final,
            stand_size_final_contribution=area_contribution,
        )

    def retrieve(self, request: FunnelInput, candidates: Sequence[Candidate]) -> FunnelResult:
        assessments = tuple(self.assess(request, candidate) for candidate in candidates)
        by_tier = {tier: [a for a in assessments if a.tier == tier] for tier in Tier}
        if not request.listing_area_reliable or request.listing_area_m2 is None:
            queue = list(by_tier[Tier.NORMAL])
            reasons = ("listing_area_unavailable_or_unreliable",)
        else:
            queue = list(by_tier[Tier.T1])
            reasons_list: list[str] = []
            t1 = by_tier[Tier.T1]
            if len(t1) < self.config.minimum_tier1_support:
                reasons_list.append("insufficient_tier1_support")
            if self._unknown_fraction(t1) >= self.config.unknown_pool_fraction_for_fallback:
                reasons_list.append("high_unknown_pool_observability")
            if request.listing_has_pool is not None and not any(
                assessment.pool_priority > 0 for assessment in t1
            ):
                reasons_list.append("no_pool_compatible_tier1_candidate")
            if self._mean_coverage(t1) < self.config.low_confidence_coverage:
                reasons_list.append("low_evidence_coverage")
            if reasons_list:
                queue.extend(by_tier[Tier.T2])
            reasons = tuple(reasons_list)

        ordered = sorted(
            queue,
            key=lambda a: (a.pool_priority, a.evidence_coverage, a.final_compatibility),
            reverse=True,
        )
        t3 = tuple(item.candidate.candidate_id for item in by_tier[Tier.T3])
        counts = {tier.value: len(by_tier[tier]) for tier in Tier}
        counts["expensive_queue"] = len(ordered)
        counts["universe"] = len(assessments)
        reduction = 0.0 if not assessments else 1.0 - len(ordered) / len(assessments)
        return FunnelResult(
            assessments=assessments,
            expensive_queue=tuple(item.candidate.candidate_id for item in ordered),
            recoverable_tier3=t3,
            expansion_reasons=reasons,
            stage_counts=counts,
            estimated_expensive_work_reduction=round(reduction, 4),
        )

    def recover_tier3(self, result: FunnelResult) -> tuple[str, ...]:
        """Return the documented, non-destructive final recovery expansion."""
        assessed = {item.candidate.candidate_id: item for item in result.assessments}
        return tuple(
            item.candidate.candidate_id
            for item in sorted(
                (assessed[candidate_id] for candidate_id in result.recoverable_tier3),
                key=lambda item: (item.pool_priority, item.evidence_coverage),
                reverse=True,
            )
        )

    def _area_metrics(
        self, request: FunnelInput, cadastral_area_m2: float | None
    ) -> tuple[float | None, float | None, Tier]:
        if (
            not request.listing_area_reliable
            or request.listing_area_m2 is None
            or request.listing_area_m2 <= 0
            or cadastral_area_m2 is None
            or cadastral_area_m2 <= 0
        ):
            return None, None, Tier.NORMAL
        absolute = abs(cadastral_area_m2 - request.listing_area_m2)
        percent = absolute / request.listing_area_m2
        if percent <= 0.10:
            tier = Tier.T1
        elif percent <= 0.20:
            tier = Tier.T2
        else:
            tier = Tier.T3
        return absolute, percent, tier

    @staticmethod
    def _pool_priority(listing_has_pool: bool | None, state: PoolState) -> float:
        if listing_has_pool is None or state == PoolState.UNKNOWN:
            return 0.0
        expected_state = (
            PoolState.OBSERVED_POOL if listing_has_pool else PoolState.OBSERVED_NO_POOL
        )
        return 1.0 if state == expected_state else -1.0

    @staticmethod
    def _coverage(candidate: Candidate) -> float:
        observed = sum(
            getattr(candidate, name) != EvidenceState.UNKNOWN for name in _SECONDARY_FIELDS
        )
        return observed / len(_SECONDARY_FIELDS)

    def _final_compatibility(
        self,
        request: FunnelInput,
        tier: Tier,
        candidate: Candidate,
        pool_state: PoolState,
    ) -> tuple[float, float]:
        # Unknown terms are neutral; only observed conflicts lower compatibility.
        feature_scores = [_STATE_SCORE[getattr(candidate, name)] for name in _SECONDARY_FIELDS]
        # Geometry has no meaning until the observed object is bound to this parcel.
        if pool_state == PoolState.OBSERVED_POOL:
            feature_scores.append(_STATE_SCORE[candidate.pool_geometry])
        observed = [score for score in feature_scores if score != 0.0]
        feature_component = sum(observed) / len(observed) if observed else 0.0
        pool_component = self._pool_priority(request.listing_has_pool, pool_state) * 0.25
        area_component = {
            Tier.T1: self.config.stand_size_final_weight,
            Tier.T2: self.config.stand_size_final_weight * 0.5,
            Tier.T3: 0.0,
            Tier.NORMAL: 0.0,
        }[tier]
        return 0.5 + 0.35 * feature_component + pool_component + area_component, area_component

    @staticmethod
    def _unknown_fraction(assessments: Sequence[CandidateAssessment]) -> float:
        if not assessments:
            return 1.0
        return sum(item.pool_state == PoolState.UNKNOWN for item in assessments) / len(assessments)

    @staticmethod
    def _mean_coverage(assessments: Sequence[CandidateAssessment]) -> float:
        if not assessments:
            return 0.0
        return sum(item.evidence_coverage for item in assessments) / len(assessments)
