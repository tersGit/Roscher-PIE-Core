"""Experimental hierarchical candidate retrieval funnel.

This package is intentionally isolated from frozen PIE ranking and detectors.
"""

from .funnel import (
    Candidate,
    EvidenceState,
    FunnelConfig,
    FunnelInput,
    FunnelResult,
    PoolObservation,
    PoolState,
    RetrievalFunnel,
    Tier,
)
from .hierarchical_v1_1 import (
    EvidenceSufficiencyAssessment,
    EvidenceSufficiencyConfig,
    ExpansionRecord,
    HierarchicalFunnelResult,
    HierarchicalRetrievalFunnelV11,
    Priority,
    StageInstrumentation,
    SufficiencyTrigger,
)
from .hierarchical_v1_2 import (
    BandResult,
    Compatibility,
    EvidenceLaneConfig,
    ExpansionTrigger as V12ExpansionTrigger,
    HierarchicalRetrievalFunnelV12,
    Lane,
    LaneAssessment,
    LaneCandidate,
    ObservableEvidence,
)

__all__ = [
    "Candidate",
    "EvidenceState",
    "FunnelConfig",
    "FunnelInput",
    "FunnelResult",
    "PoolObservation",
    "PoolState",
    "RetrievalFunnel",
    "Tier",
    "EvidenceSufficiencyAssessment",
    "EvidenceSufficiencyConfig",
    "ExpansionRecord",
    "HierarchicalFunnelResult",
    "HierarchicalRetrievalFunnelV11",
    "Priority",
    "StageInstrumentation",
    "SufficiencyTrigger",
    "BandResult",
    "Compatibility",
    "EvidenceLaneConfig",
    "V12ExpansionTrigger",
    "HierarchicalRetrievalFunnelV12",
    "Lane",
    "LaneAssessment",
    "LaneCandidate",
    "ObservableEvidence",
]
