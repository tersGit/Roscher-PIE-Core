"""Experimental evidence/recovery lanes for hierarchical retrieval v1.2.

This module is deliberately not connected to production scoring or v1/v1.1.
It routes already-observed parcel evidence; it does not run detectors, infer
identities, or turn an unknown observation into a negative claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class Lane(str, Enum):
    EVIDENCE = "EVIDENCE"
    RECOVERY = "RECOVERY"


class Compatibility(str, Enum):
    STRONG_MATCH = "STRONG_MATCH"
    MATCH = "MATCH"
    PARTIAL = "PARTIAL"
    VISIBLE_CONFLICT = "VISIBLE_CONFLICT"
    UNKNOWN = "UNKNOWN"


class ExpansionTrigger(str, Enum):
    NO_STRONG_EVIDENCE_LANE = "NO_STRONG_EVIDENCE_LANE"
    EVIDENCE_LANE_VISIBLE_CONFLICT = "EVIDENCE_LANE_VISIBLE_CONFLICT"
    INSUFFICIENT_DISTINCTIVE_SUPPORT = "INSUFFICIENT_DISTINCTIVE_SUPPORT"
    RECOVERY_LANE_PROMOTIONS_INSUFFICIENT = "RECOVERY_LANE_PROMOTIONS_INSUFFICIENT"


@dataclass(frozen=True)
class ObservableEvidence:
    """A parcel-bound target discriminator, not generic object observability."""

    observable: bool = False
    parcel_bound: bool = False
    compatibility: Compatibility = Compatibility.UNKNOWN
    distinctive_components: int = 0

    @property
    def strong(self) -> bool:
        return (
            self.observable
            and self.parcel_bound
            and self.compatibility == Compatibility.STRONG_MATCH
        )

    @property
    def visible_conflict(self) -> bool:
        return self.observable and self.compatibility == Compatibility.VISIBLE_CONFLICT


@dataclass(frozen=True)
class LaneCandidate:
    candidate_id: str
    area_band: str
    pool_geometry: ObservableEvidence = ObservableEvidence()
    building_geometry: ObservableEvidence = ObservableEvidence()


@dataclass(frozen=True)
class LaneAssessment:
    candidate_id: str
    initial_lane: Lane
    final_lane: Lane
    promoted: bool
    demoted: bool
    recoverable: bool
    evidence_strength: int
    distinctiveness: int
    visible_conflicts: int


@dataclass(frozen=True)
class BandResult:
    area_band: str
    evidence_candidate_ids: tuple[str, ...]
    recovery_candidate_ids: tuple[str, ...]
    cheap_recovery_pass_ids: tuple[str, ...]
    promotion_ids: tuple[str, ...]
    demotion_ids: tuple[str, ...]
    expensive_candidate_ids: tuple[str, ...]
    triggers: tuple[ExpansionTrigger, ...]
    stopped: bool
    assessments: tuple[LaneAssessment, ...]


@dataclass(frozen=True)
class EvidenceLaneConfig:
    minimum_distinctiveness: int = 1
    minimum_stop_candidates: int = 5
    maximum_stop_candidates: int = 20


class HierarchicalRetrievalFunnelV12:
    """Prioritize strong, parcel-bound discriminators while retaining recovery."""

    def __init__(self, config: EvidenceLaneConfig = EvidenceLaneConfig()) -> None:
        self.config = config

    def process_band(self, area_band: str, candidates: Sequence[LaneCandidate]) -> BandResult:
        initial_evidence = [
            candidate for candidate in candidates if candidate.pool_geometry.strong
        ]
        recovery = [
            candidate for candidate in candidates if candidate not in initial_evidence
        ]
        promotions = [
            candidate for candidate in recovery if candidate.building_geometry.strong
        ]
        final_evidence = initial_evidence + promotions
        demotions = [
            candidate for candidate in final_evidence
            if candidate.building_geometry.visible_conflict
        ]
        final_evidence = [
            candidate for candidate in final_evidence if candidate not in demotions
        ]
        recovery_ids = tuple(
            candidate.candidate_id
            for candidate in candidates
            if candidate not in final_evidence
        )
        assessments = tuple(
            self._assess(candidate, candidate in initial_evidence, candidate in promotions,
                         candidate in demotions)
            for candidate in candidates
        )
        expensive = tuple(
            assessment.candidate_id
            for assessment in sorted(
                (assessment for assessment in assessments if assessment.final_lane == Lane.EVIDENCE),
                key=lambda assessment: (
                    assessment.evidence_strength,
                    assessment.distinctiveness,
                    -assessment.visible_conflicts,
                    assessment.candidate_id,
                ),
                reverse=True,
            )
        )
        triggers = self._triggers(
            initial_evidence, promotions, final_evidence, assessments
        )
        stopped = (
            not triggers
            and self.config.minimum_stop_candidates <= len(expensive)
            <= self.config.maximum_stop_candidates
        )
        return BandResult(
            area_band=area_band,
            evidence_candidate_ids=tuple(candidate.candidate_id for candidate in initial_evidence),
            recovery_candidate_ids=recovery_ids,
            cheap_recovery_pass_ids=tuple(candidate.candidate_id for candidate in recovery),
            promotion_ids=tuple(candidate.candidate_id for candidate in promotions),
            demotion_ids=tuple(candidate.candidate_id for candidate in demotions),
            expensive_candidate_ids=expensive,
            triggers=triggers,
            stopped=stopped,
            assessments=assessments,
        )

    def _assess(
        self,
        candidate: LaneCandidate,
        initially_evidence: bool,
        promoted: bool,
        demoted: bool,
    ) -> LaneAssessment:
        evidence = (candidate.pool_geometry, candidate.building_geometry)
        strength = sum(item.strong for item in evidence)
        distinctiveness = sum(
            item.distinctive_components for item in evidence if item.strong
        )
        conflicts = sum(item.visible_conflict for item in evidence)
        return LaneAssessment(
            candidate_id=candidate.candidate_id,
            initial_lane=Lane.EVIDENCE if initially_evidence else Lane.RECOVERY,
            final_lane=Lane.RECOVERY if demoted else (
                Lane.EVIDENCE if initially_evidence or promoted else Lane.RECOVERY
            ),
            promoted=promoted,
            demoted=demoted,
            recoverable=True,
            evidence_strength=strength,
            distinctiveness=distinctiveness,
            visible_conflicts=conflicts,
        )

    def _triggers(
        self,
        initial_evidence: Sequence[LaneCandidate],
        promotions: Sequence[LaneCandidate],
        final_evidence: Sequence[LaneCandidate],
        assessments: Sequence[LaneAssessment],
    ) -> tuple[ExpansionTrigger, ...]:
        triggers: list[ExpansionTrigger] = []
        if not initial_evidence:
            triggers.append(ExpansionTrigger.NO_STRONG_EVIDENCE_LANE)
        if any(assessment.demoted for assessment in assessments):
            triggers.append(ExpansionTrigger.EVIDENCE_LANE_VISIBLE_CONFLICT)
        if final_evidence and max(
            assessment.distinctiveness for assessment in assessments
            if assessment.final_lane == Lane.EVIDENCE
        ) < self.config.minimum_distinctiveness:
            triggers.append(ExpansionTrigger.INSUFFICIENT_DISTINCTIVE_SUPPORT)
        if not final_evidence or (
            not promotions and len(final_evidence) < self.config.minimum_stop_candidates
        ):
            triggers.append(ExpansionTrigger.RECOVERY_LANE_PROMOTIONS_INSUFFICIENT)
        return tuple(triggers)
