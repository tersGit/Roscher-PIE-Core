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
]
