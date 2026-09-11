"""Experimental v1.1 hierarchical retrieval ordering.

This module consumes the same conservative candidate observations as Funnel v1,
but changes only the order in which groups receive the safe evidence sequence.
It is not connected to production scoring, ranking, detectors, or VLMs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from .funnel import Candidate, CandidateAssessment, EvidenceState, FunnelInput, RetrievalFunnel


class Priority(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    NORMAL = "NORMAL"


class SufficiencyTrigger(str, Enum):
    NO_ADEQUATE_CANDIDATES = "NO_ADEQUATE_CANDIDATES"
    LOW_TOP_CANDIDATE_COVERAGE = "LOW_TOP_CANDIDATE_COVERAGE"
    NON_UNIQUE_TOP_SET = "NON_UNIQUE_TOP_SET"
    MATERIAL_VISIBLE_CONFLICTS = "MATERIAL_VISIBLE_CONFLICTS"
    INSUFFICIENT_COMBINED_SUPPORT = "INSUFFICIENT_COMBINED_SUPPORT"


@dataclass(frozen=True)
class EvidenceSufficiencyConfig:
    """Pre-registered, evidence-only thresholds for a recoverable expansion."""

    serious_candidate_minimum_compatibility: float = 0.60
    minimum_top_coverage: float = 0.35
    non_unique_score_margin: float = 0.05
    maximum_non_unique_top_candidates: int = 3
    maximum_top_visible_conflicts: int = 0
    minimum_top_observable_components: int = 3
    minimum_combined_support: float = 0.60


@dataclass(frozen=True)
class EvidenceSufficiencyAssessment:
    serious_candidate_ids: tuple[str, ...]
    top_candidate_id: str | None
    top_candidate_coverage: float
    top_candidate_support_count: int
    top_candidate_visible_conflicts: int
    combined_support: float
    non_unique_top_set_size: int
    triggers: tuple[SufficiencyTrigger, ...]

    @property
    def sufficient(self) -> bool:
        return not self.triggers


@dataclass(frozen=True)
class StageInstrumentation:
    priority: Priority
    candidate_count: int
    pool_observed_count: int
    pool_unknown_count: int
    building_observable_count: int
    average_coverage: float
    serious_candidate_count: int


@dataclass(frozen=True)
class ExpansionRecord:
    expanded: bool
    from_priority: Priority
    to_priority: Priority | None
    triggers: tuple[SufficiencyTrigger, ...]


@dataclass(frozen=True)
class HierarchicalFunnelResult:
    assessments: tuple[CandidateAssessment, ...]
    processed_candidate_ids: tuple[str, ...]
    recoverable_candidate_ids: tuple[str, ...]
    stage_instrumentation: tuple[StageInstrumentation, ...]
    sufficiency_assessments: tuple[EvidenceSufficiencyAssessment, ...]
    expansions: tuple[ExpansionRecord, ...]
    priority_counts: dict[str, int]
    immediate_expensive_workload: int
    total_expensive_workload: int


class HierarchicalRetrievalFunnelV11:
    """Run A, then expand B/C/D only after an evidence sufficiency assessment."""

    def __init__(
        self,
        base_funnel: RetrievalFunnel | None = None,
        config: EvidenceSufficiencyConfig = EvidenceSufficiencyConfig(),
    ) -> None:
        self.base_funnel = base_funnel or RetrievalFunnel()
        self.config = config

    def priority_for(self, request: FunnelInput, candidate: Candidate) -> Priority:
        if (
            not request.listing_area_reliable
            or request.listing_area_m2 is None
            or request.listing_area_m2 <= 0
            or candidate.cadastral_area_m2 is None
            or candidate.cadastral_area_m2 <= 0
        ):
            return Priority.NORMAL
        difference = abs(candidate.cadastral_area_m2 - request.listing_area_m2)
        percent = difference / request.listing_area_m2
        if percent <= 0.05:
            return Priority.A
        if percent <= 0.10:
            return Priority.B
        if percent <= 0.20:
            return Priority.C
        return Priority.D

    def retrieve(
        self, request: FunnelInput, candidates: Sequence[Candidate]
    ) -> HierarchicalFunnelResult:
        assessments = tuple(self.base_funnel.assess(request, candidate) for candidate in candidates)
        by_priority = {
            priority: [
                assessment
                for assessment in assessments
                if self.priority_for(request, assessment.candidate) == priority
            ]
            for priority in Priority
        }
        if by_priority[Priority.NORMAL]:
            normal = tuple(by_priority[Priority.NORMAL])
            sufficiency = self.assess_evidence(normal)
            return HierarchicalFunnelResult(
                assessments=assessments,
                processed_candidate_ids=tuple(item.candidate.candidate_id for item in normal),
                recoverable_candidate_ids=tuple(item.candidate.candidate_id for item in normal),
                stage_instrumentation=(self._instrument(Priority.NORMAL, normal),),
                sufficiency_assessments=(sufficiency,),
                expansions=(),
                priority_counts=self._priority_counts(by_priority),
                immediate_expensive_workload=len(normal),
                total_expensive_workload=len(normal),
            )

        processed: list[CandidateAssessment] = []
        instrumentation: list[StageInstrumentation] = []
        sufficiency_assessments: list[EvidenceSufficiencyAssessment] = []
        expansions: list[ExpansionRecord] = []
        immediate_workload = len(by_priority[Priority.A])
        priorities = (Priority.A, Priority.B, Priority.C, Priority.D)
        for index, priority in enumerate(priorities):
            processed.extend(by_priority[priority])
            sufficiency = self.assess_evidence(processed)
            instrumentation.append(self._instrument(priority, by_priority[priority]))
            sufficiency_assessments.append(sufficiency)
            next_priority = priorities[index + 1] if index + 1 < len(priorities) else None
            expands = bool(next_priority and not sufficiency.sufficient)
            expansions.append(
                ExpansionRecord(
                    expanded=expands,
                    from_priority=priority,
                    to_priority=next_priority if expands else None,
                    triggers=sufficiency.triggers,
                )
            )
            if not expands:
                break

        processed_ids = tuple(item.candidate.candidate_id for item in processed)
        recoverable_ids = tuple(
            item.candidate.candidate_id
            for priority in priorities
            for item in by_priority[priority]
            if item.candidate.candidate_id not in set(processed_ids)
        )
        return HierarchicalFunnelResult(
            assessments=assessments,
            processed_candidate_ids=processed_ids,
            recoverable_candidate_ids=recoverable_ids,
            stage_instrumentation=tuple(instrumentation),
            sufficiency_assessments=tuple(sufficiency_assessments),
            expansions=tuple(expansions),
            priority_counts=self._priority_counts(by_priority),
            immediate_expensive_workload=immediate_workload,
            total_expensive_workload=len(processed_ids),
        )

    def assess_evidence(
        self, assessments: Sequence[CandidateAssessment]
    ) -> EvidenceSufficiencyAssessment:
        ordered = sorted(
            assessments,
            key=lambda item: (item.final_compatibility, item.evidence_coverage),
            reverse=True,
        )
        serious = tuple(
            item
            for item in ordered
            if item.final_compatibility >= self.config.serious_candidate_minimum_compatibility
        )
        top = serious[0] if serious else None
        top_score = top.final_compatibility if top else 0.0
        non_unique = tuple(
            item
            for item in serious
            if top_score - item.final_compatibility <= self.config.non_unique_score_margin
        )
        coverage = top.evidence_coverage if top else 0.0
        support_count = self._support_count(top.candidate) if top else 0
        conflicts = self._conflict_count(top.candidate) if top else 0
        combined = (
            (
                top.final_compatibility
                + coverage
                + min(support_count / 8, 1.0)
            ) / 3
            if top
            else 0.0
        )
        triggers: list[SufficiencyTrigger] = []
        if not serious:
            triggers.append(SufficiencyTrigger.NO_ADEQUATE_CANDIDATES)
        if coverage < self.config.minimum_top_coverage:
            triggers.append(SufficiencyTrigger.LOW_TOP_CANDIDATE_COVERAGE)
        if len(non_unique) > self.config.maximum_non_unique_top_candidates:
            triggers.append(SufficiencyTrigger.NON_UNIQUE_TOP_SET)
        if conflicts > self.config.maximum_top_visible_conflicts:
            triggers.append(SufficiencyTrigger.MATERIAL_VISIBLE_CONFLICTS)
        if (
            support_count < self.config.minimum_top_observable_components
            or combined < self.config.minimum_combined_support
        ):
            triggers.append(SufficiencyTrigger.INSUFFICIENT_COMBINED_SUPPORT)
        return EvidenceSufficiencyAssessment(
            serious_candidate_ids=tuple(item.candidate.candidate_id for item in serious),
            top_candidate_id=top.candidate.candidate_id if top else None,
            top_candidate_coverage=coverage,
            top_candidate_support_count=support_count,
            top_candidate_visible_conflicts=conflicts,
            combined_support=combined,
            non_unique_top_set_size=len(non_unique),
            triggers=tuple(triggers),
        )

    def _instrument(
        self,
        priority: Priority,
        stage: Sequence[CandidateAssessment],
    ) -> StageInstrumentation:
        stage_sufficiency = self.assess_evidence(stage)
        return StageInstrumentation(
            priority=priority,
            candidate_count=len(stage),
            pool_observed_count=sum(item.pool_state.value != "UNKNOWN" for item in stage),
            pool_unknown_count=sum(item.pool_state.value == "UNKNOWN" for item in stage),
            building_observable_count=sum(
                item.candidate.building != EvidenceState.UNKNOWN for item in stage
            ),
            average_coverage=round(
                sum(item.evidence_coverage for item in stage) / len(stage), 4
            ) if stage else 0.0,
            serious_candidate_count=len(stage_sufficiency.serious_candidate_ids),
        )

    @staticmethod
    def _priority_counts(
        by_priority: dict[Priority, list[CandidateAssessment]]
    ) -> dict[str, int]:
        counts = {priority.value: len(by_priority[priority]) for priority in Priority}
        counts["universe"] = sum(counts.values())
        return counts

    @staticmethod
    def _support_count(candidate: Candidate) -> int:
        fields = (
            "building", "roof", "house_pool", "pool_geometry", "solar",
            "driveway_garage", "open_space", "neighbour_context",
        )
        return sum(getattr(candidate, name) in (EvidenceState.MATCH, EvidenceState.PARTIAL) for name in fields)

    @staticmethod
    def _conflict_count(candidate: Candidate) -> int:
        fields = (
            "building", "roof", "house_pool", "pool_geometry", "solar",
            "driveway_garage", "open_space", "neighbour_context",
        )
        return sum(getattr(candidate, name) == EvidenceState.CONFLICT for name in fields)
