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
]
