"""Authorized-source video acquisition helpers."""

from .youtube_acquire import (
    AcquisitionFailure,
    AcquisitionResult,
    FailureCategory,
    acquire_youtube_video,
)

__all__ = [
    "AcquisitionFailure",
    "AcquisitionResult",
    "FailureCategory",
    "acquire_youtube_video",
]
