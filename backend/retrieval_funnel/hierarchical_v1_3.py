"""High-confidence cadastral stand-size entry gate for Funnel v1.3.

This experimental module only selects the cadastral candidate work universe.
It neither calls visual code nor changes scoring, evidence lanes, recovery
semantics, geometry logic, detectors, or existing funnel implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class AreaConfidence(str, Enum):
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class ListingAreaSource(str, Enum):
    ERF_SIZE = "ERF_SIZE"
    LAND_SIZE = "LAND_SIZE"
    STRUCTURED_METADATA = "STRUCTURED_METADATA"
    REPEATED_SPECIFIC_FIGURE = "REPEATED_SPECIFIC_FIGURE"
    MARKETING_COPY = "MARKETING_COPY"
    INFERRED = "INFERRED"


class AreaQualifier(str, Enum):
    EXACT = "EXACT"
    APPROXIMATE = "APPROXIMATE"
    ROUNDED = "ROUNDED"
    INFERRED = "INFERRED"


class RescueTrigger(str, Enum):
    NO_CREDIBLE_CANDIDATES = "NO_CREDIBLE_CANDIDATES"
    ALL_TOP_CANDIDATES_VISIBLE_CONFLICT = "ALL_TOP_CANDIDATES_VISIBLE_CONFLICT"
    LISTING_AREA_CONFIDENCE_DOWNGRADED = "LISTING_AREA_CONFIDENCE_DOWNGRADED"
    EVIDENCE_SUGGESTS_LISTING_AREA_ERROR = "EVIDENCE_SUGGESTS_LISTING_AREA_ERROR"
    CADASTRAL_AREA_DATA_QUALITY_WARNING = "CADASTRAL_AREA_DATA_QUALITY_WARNING"


@dataclass(frozen=True)
class ListingAreaFact:
    square_metres: float | None
    source: ListingAreaSource
    qualifier: AreaQualifier = AreaQualifier.EXACT
    unit: str = "m2"


@dataclass(frozen=True)
class ListingAreaAssessment:
    square_metres: float | None
    confidence: AreaConfidence
    reason: str


class ListingAreaClassifier:
    """Classify listing facts conservatively before allowing a hard gate."""

    def classify(self, facts: Sequence[ListingAreaFact]) -> ListingAreaAssessment:
        usable = [
            fact for fact in facts
            if fact.square_metres is not None and fact.square_metres > 0
        ]
        if not usable:
            return ListingAreaAssessment(None, AreaConfidence.UNKNOWN, "missing_or_inferred")
        if any(fact.qualifier == AreaQualifier.INFERRED for fact in usable):
            return ListingAreaAssessment(None, AreaConfidence.UNKNOWN, "inferred_area")
        values = {fact.square_metres for fact in usable}
        if len(values) != 1:
            return ListingAreaAssessment(None, AreaConfidence.MEDIUM, "conflicting_figures")
        value = usable[0].square_metres
        if any(fact.qualifier == AreaQualifier.APPROXIMATE for fact in usable):
            return ListingAreaAssessment(value, AreaConfidence.LOW, "approximate_area")
        if any(fact.qualifier == AreaQualifier.ROUNDED for fact in usable):
            return ListingAreaAssessment(value, AreaConfidence.MEDIUM, "rounded_marketing_area")
        high_sources = {ListingAreaSource.ERF_SIZE, ListingAreaSource.LAND_SIZE}
        if any(fact.source in high_sources for fact in usable):
            return ListingAreaAssessment(value, AreaConfidence.HIGH_CONFIDENCE, "explicit_erf_or_land_size")
        structured = [
            fact for fact in usable
            if fact.source == ListingAreaSource.STRUCTURED_METADATA
            and fact.unit == "m2"
        ]
        if structured:
            return ListingAreaAssessment(value, AreaConfidence.HIGH_CONFIDENCE, "specific_structured_m2")
        repeated = [
            fact for fact in usable
            if fact.source == ListingAreaSource.REPEATED_SPECIFIC_FIGURE
        ]
        if len(repeated) >= 2:
            return ListingAreaAssessment(value, AreaConfidence.HIGH_CONFIDENCE, "consistent_specific_repetition")
        return ListingAreaAssessment(value, AreaConfidence.MEDIUM, "unqualified_marketing_figure")


class StandSizePriority(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    NORMAL = "NORMAL"


@dataclass(frozen=True)
class StandSizeCandidate:
    candidate_id: str
    cadastral_area_m2: float | None


@dataclass(frozen=True)
class RescueActivation:
    activated: bool
    levels: tuple[StandSizePriority, ...]
    triggers: tuple[RescueTrigger, ...]


@dataclass(frozen=True)
class StandSizeGateResult:
    listing_area_m2: float | None
    listing_area_confidence: AreaConfidence
    lower_bound_m2: float | None
    upper_bound_m2: float | None
    normal_candidate_ids: tuple[str, ...]
    priority_a_ids: tuple[str, ...]
    priority_b_ids: tuple[str, ...]
    exceptional_rescue_ids: tuple[str, ...]
    rescue_c_ids: tuple[str, ...]
    rescue_d_ids: tuple[str, ...]
    excluded_from_ordinary_queue_ids: tuple[str, ...]
    gate_enabled: bool

    def instrumentation(self, rescue: RescueActivation | None = None) -> dict[str, object]:
        rescue = rescue or RescueActivation(False, (), ())
        return {
            "listing_area_m2": self.listing_area_m2,
            "listing_area_confidence": self.listing_area_confidence.value,
            "plus_minus_10_lower_m2": self.lower_bound_m2,
            "plus_minus_10_upper_m2": self.upper_bound_m2,
            "normal_count": len(self.normal_candidate_ids),
            "priority_a_count": len(self.priority_a_ids),
            "priority_b_count": len(self.priority_b_ids),
            "excluded_ordinary_count": len(self.excluded_from_ordinary_queue_ids),
            "exceptional_rescue_count": len(self.exceptional_rescue_ids),
            "rescue_activated": rescue.activated,
            "rescue_trigger": [trigger.value for trigger in rescue.triggers],
            "rescue_levels": [level.value for level in rescue.levels],
        }


class HighConfidenceStandSizeGate:
    """Apply the v1.3 gate only where listing area confidence is high."""

    def select(
        self, assessment: ListingAreaAssessment, candidates: Sequence[StandSizeCandidate]
    ) -> StandSizeGateResult:
        enabled = (
            assessment.confidence == AreaConfidence.HIGH_CONFIDENCE
            and assessment.square_metres is not None
            and assessment.square_metres > 0
        )
        if not enabled:
            ids = tuple(candidate.candidate_id for candidate in candidates)
            return StandSizeGateResult(
                assessment.square_metres, assessment.confidence, None, None, ids, (), (),
                (), (), (), (), False,
            )
        area = assessment.square_metres
        bands = {priority: [] for priority in StandSizePriority}
        for candidate in candidates:
            priority = self._priority(area, candidate.cadastral_area_m2)
            bands[priority].append(candidate.candidate_id)
        normal = tuple(bands[StandSizePriority.A] + bands[StandSizePriority.B])
        rescue_c = tuple(bands[StandSizePriority.C])
        rescue_d = tuple(bands[StandSizePriority.D])
        exceptional = rescue_c + rescue_d
        return StandSizeGateResult(
            area, assessment.confidence, area * 0.9, area * 1.1, normal,
            tuple(bands[StandSizePriority.A]), tuple(bands[StandSizePriority.B]),
            exceptional, rescue_c, rescue_d, exceptional, True,
        )

    def activate_rescue(
        self,
        result: StandSizeGateResult,
        triggers: Sequence[RescueTrigger],
        c_failed_eligible_criterion: bool = False,
    ) -> RescueActivation:
        if any(not isinstance(trigger, RescueTrigger) for trigger in triggers):
            raise ValueError("Rescue activation requires a predefined evidence-based trigger.")
        eligible = tuple(dict.fromkeys(triggers))
        if not result.gate_enabled or not eligible:
            return RescueActivation(False, (), eligible)
        levels: tuple[StandSizePriority, ...] = (StandSizePriority.C,)
        if c_failed_eligible_criterion:
            levels += (StandSizePriority.D,)
        return RescueActivation(True, levels, eligible)

    @staticmethod
    def _priority(listing_area_m2: float, cadastral_area_m2: float | None) -> StandSizePriority:
        if cadastral_area_m2 is None or cadastral_area_m2 <= 0:
            return StandSizePriority.D
        difference = abs(cadastral_area_m2 - listing_area_m2) / listing_area_m2
        if difference <= 0.05:
            return StandSizePriority.A
        if difference <= 0.10:
            return StandSizePriority.B
        if difference <= 0.15:
            return StandSizePriority.C
        return StandSizePriority.D
