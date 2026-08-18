"""Listing-side corner evidence for Corner Stand Detection v1.

LISTING_CORNER is YES / NO / UNKNOWN from listing media and text only.
Known stand identity is not an input. Absence of a second street in
photographs is not evidence of non-corner status (that stays UNKNOWN).
Listing NO requires positive non-corner evidence, not missing evidence.
"""

from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Mapping, Sequence

import numpy as np
from PIL import Image

CornerStatus = Literal["YES", "NO", "UNKNOWN"]
VALID = frozenset({"YES", "NO", "UNKNOWN"})

HIGH_YES_CONFIDENCE = 0.80
EXCEPTIONAL_NO_CONFIDENCE = 0.92

YES_TEXT_PATTERNS = (
    r"\bcorner\s+stand\b",
    r"\bcorner\s+(?:property|erf|plot|lot|home|house)\b",
    r"\bsituated\s+on\s+the\s+corner\b",
    r"\bon\s+the\s+corner\s+of\b",
    r"\bdual\s+(?:road|street)\s+frontage\b",
    r"\btwo\s+(?:road|street)\s+frontages\b",
    r"\bcorner\s+(?:position|location)\b",
)
NO_TEXT_PATTERNS = (
    r"\bnot\s+a\s+corner\b",
    r"\bmid[-\s]?block\b",
    r"\bsingle\s+(?:road|street)\s+frontage\b",
    r"\bone\s+street\s+frontage\s+only\b",
    r"\binternal\s+stand\s+(?:not|with no)\s+(?:on\s+)?(?:a\s+)?corner\b",
)
FALSE_CORNER_TEXT = re.compile(
    r"\bcorner\s+(?:of\s+the|bath|lounge|kitchen|bedroom|sofa|desk|shower)\b",
    re.I,
)

AERIAL_HINTS = frozenset({"aerial", "aerial_near_nadir", "elevated_exterior"})
VIDEO_HINTS = frozenset({"video", "video_frame"})


def normalize_corner_status(value: Any) -> CornerStatus:
    status = str(value or "UNKNOWN").strip().upper()
    if status not in VALID:
        return "UNKNOWN"
    return status  # type: ignore[return-value]


def _cv2():
    import cv2

    return cv2


def _bgr(image: Image.Image | np.ndarray | bytes) -> np.ndarray:
    cv2 = _cv2()
    if isinstance(image, (bytes, bytearray)):
        arr = np.frombuffer(image, dtype=np.uint8)
        decoded = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if decoded is None:
            pil = Image.open(io.BytesIO(image)).convert("RGB")
            return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        return decoded
    if isinstance(image, Image.Image):
        return cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    array = np.asarray(image)
    if array.ndim == 3 and array.shape[2] == 3:
        # assume RGB if coming from PIL-like arrays with high green lawns; callers pass BGR or RGB.
        return array
    if array.ndim == 2:
        return cv2.cvtColor(array, cv2.COLOR_GRAY2BGR)
    raise TypeError("unsupported image type")


def extract_corner_text_hits(text: str | None) -> dict[str, Any]:
    blob = str(text or "")
    yes_hits = []
    no_hits = []
    if not blob.strip():
        return {"yes_hits": [], "no_hits": [], "yes": False, "no": False}
    cleaned = FALSE_CORNER_TEXT.sub(" ", blob)
    for pattern in YES_TEXT_PATTERNS:
        for match in re.finditer(pattern, cleaned, flags=re.I):
            yes_hits.append(match.group(0))
    for pattern in NO_TEXT_PATTERNS:
        for match in re.finditer(pattern, blob, flags=re.I):
            no_hits.append(match.group(0))
    return {
        "yes_hits": yes_hits,
        "no_hits": no_hits,
        "yes": bool(yes_hits),
        "no": bool(no_hits) and not yes_hits,
    }


def _border_strips(gray: np.ndarray, frac: float = 0.18) -> dict[str, np.ndarray]:
    h, w = gray.shape[:2]
    dy = max(int(h * frac), 8)
    dx = max(int(w * frac), 8)
    return {
        "top": gray[:dy, :],
        "bottom": gray[h - dy :, :],
        "left": gray[:, :dx],
        "right": gray[:, w - dx :],
    }


def _pavement_score(strip: np.ndarray, night: bool) -> float:
    if strip.size == 0:
        return 0.0
    mean = float(strip.mean())
    std = float(strip.std())
    dark_frac = float((strip < (48 if night else 110)).mean())
    bright_frac = float((strip > (170 if night else 200)).mean())
    # Night roads: dark asphalt plus sparse street-light speckles.
    if night:
        linear = 0.0
        if strip.shape[0] >= 6 and strip.shape[1] >= 6:
            row_var = float(np.mean(np.var(strip, axis=1)))
            col_var = float(np.mean(np.var(strip, axis=0)))
            linear = min(row_var, col_var) / max(max(row_var, col_var), 1.0)
        score = 0.55 * dark_frac + 0.25 * min(bright_frac * 12.0, 1.0) + 0.20 * (1.0 - min(mean / 80.0, 1.0))
        if std < 8:
            score *= 0.4
        return float(min(max(score, 0.0), 1.0))
    mid = float(((strip > 70) & (strip < 185)).mean())
    score = 0.45 * mid + 0.25 * dark_frac + 0.15 * min(std / 40.0, 1.0) + 0.15 * min(bright_frac * 8.0, 1.0)
    return float(min(max(score, 0.0), 1.0))


def _hough_border_orientations(gray: np.ndarray) -> list[float]:
    cv2 = _cv2()
    h, w = gray.shape[:2]
    mask = np.zeros_like(gray)
    dy, dx = max(int(h * 0.20), 8), max(int(w * 0.20), 8)
    mask[:dy, :] = 255
    mask[h - dy :, :] = 255
    mask[:, :dx] = 255
    mask[:, w - dx :] = 255
    edges = cv2.Canny(gray, 40, 120)
    edges = cv2.bitwise_and(edges, mask)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180.0, threshold=28, minLineLength=int(min(h, w) * 0.18), maxLineGap=12)
    if lines is None:
        return []
    packed = np.asarray(lines).reshape(-1, 4)
    headings = []
    for line in packed:
        x0, y0, x1, y1 = (float(v) for v in line[:4])
        headings.append((math.degrees(math.atan2(y1 - y0, x1 - x0)) % 180.0, math.hypot(x1 - x0, y1 - y0)))
    headings.sort(key=lambda item: -item[1])
    return [h for h, _ in headings[:12]]


def _distinct_heading_pair(headings: Sequence[float]) -> tuple[bool, float | None]:
    best = None
    for i, a in enumerate(headings):
        for b in headings[i + 1 :]:
            d = abs(a - b) % 180.0
            if d > 90.0:
                d = 180.0 - d
            if d >= 35.0 and (best is None or d > best):
                best = d
    return best is not None, best


def inspect_frame_roads(
    image: Image.Image | np.ndarray | bytes,
    *,
    media_id: str | None = None,
    viewpoint: str | None = None,
) -> dict[str, Any]:
    """Geometric road-border evidence. Does not look up stand identity."""
    cv2 = _cv2()
    bgr = _bgr(image)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    night = float(gray.mean()) < 90.0
    strips = _border_strips(gray)
    side_scores = {side: round(_pavement_score(strip, night), 4) for side, strip in strips.items()}
    strong = [side for side, score in side_scores.items() if score >= 0.42]
    adjacent_pairs = (("top", "left"), ("top", "right"), ("bottom", "left"), ("bottom", "right"))
    adjacent = [pair for pair in adjacent_pairs if pair[0] in strong and pair[1] in strong]
    headings = _hough_border_orientations(gray)
    two_headings, heading_sep = _distinct_heading_pair(headings)
    viewpoint_l = str(viewpoint or "").lower()
    aerial = viewpoint_l in AERIAL_HINTS
    two_sides = len(strong) >= 2 and bool(adjacent)
    visual_yes = False
    visual_conf = 0.0
    reason = "no_second_road_visible_unknown_not_no"
    eligible = aerial or viewpoint_l in VIDEO_HINTS
    if not eligible:
        reason = "non_aerial_frame_not_used_for_corner_visual"
    elif two_sides and (two_headings or night):
        visual_yes = True
        visual_conf = 0.78
        if night and two_sides:
            visual_conf += 0.08
        if two_headings and heading_sep and heading_sep >= 55:
            visual_conf += 0.08
        visual_conf = min(visual_conf, 0.96)
        reason = "roads_visible_along_two_parcel_sides"
        if night:
            reason = "night_aerial_roads_along_front_and_side_boundaries"
    elif len(strong) == 1:
        reason = "only_one_visible_road_border_unknown_not_no"
        visual_conf = 0.0
    return {
        "media_id": media_id,
        "viewpoint": viewpoint,
        "night": night,
        "side_scores": side_scores,
        "strong_sides": strong,
        "adjacent_strong_pairs": [list(pair) for pair in adjacent],
        "two_heading_axes": two_headings,
        "heading_separation_deg": None if heading_sep is None else round(heading_sep, 2),
        "visual_yes": visual_yes,
        "visual_confidence": round(visual_conf, 4),
        "reason": reason,
    }


@dataclass
class ListingCornerEvidence:
    classification: CornerStatus
    confidence: float
    evidence_source: str
    frame_ids: list[str] = field(default_factory=list)
    text_evidence: list[str] = field(default_factory=list)
    aerial_evidence: bool = False
    video_evidence: bool = False
    visual_reason: str = ""
    contradiction_flags: list[str] = field(default_factory=list)
    high_confidence: bool = False
    exceptional_non_corner: bool = False
    positive_non_corner_evidence: bool = False
    frames: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "listing_corner": self.classification,
            "classification": self.classification,
            "confidence": self.confidence,
            "evidence_source": self.evidence_source,
            "frame_ids": list(self.frame_ids),
            "text_evidence": list(self.text_evidence),
            "aerial_evidence": self.aerial_evidence,
            "video_evidence": self.video_evidence,
            "visual_reason": self.visual_reason,
            "contradiction_flags": list(self.contradiction_flags),
            "high_confidence": self.high_confidence,
            "exceptional_non_corner": self.exceptional_non_corner,
            "positive_non_corner_evidence": self.positive_non_corner_evidence,
            "frames": list(self.frames),
        }


def observe_listing_corner(
    *,
    text: str | None = None,
    photos: Mapping[str, Any] | None = None,
    frames: Sequence[Mapping[str, Any]] | None = None,
    viewpoints: Mapping[str, str] | None = None,
) -> ListingCornerEvidence:
    """Classify listing corner evidence. photos: media_id → bytes/PIL/ndarray."""
    text_hits = extract_corner_text_hits(text)
    observations: list[dict[str, Any]] = []
    views = dict(viewpoints or {})
    items: list[tuple[str, Any, str | None]] = []
    if photos:
        for media_id, body in photos.items():
            items.append((str(media_id), body, views.get(str(media_id))))
    if frames:
        for frame in frames:
            media_id = str(frame.get("media_id") or frame.get("frame_id") or f"frame_{len(items)}")
            body = frame.get("image") or frame.get("bytes") or frame.get("bgr")
            if body is None:
                continue
            viewpoint = frame.get("viewpoint") or views.get(media_id)
            items.append((media_id, body, None if viewpoint is None else str(viewpoint)))

    for media_id, body, viewpoint in items:
        obs = inspect_frame_roads(body, media_id=media_id, viewpoint=viewpoint)
        observations.append(obs)

    visual_yes = [row for row in observations if row.get("visual_yes")]
    aerial_yes = [
        row
        for row in visual_yes
        if str(row.get("viewpoint") or "").lower() in AERIAL_HINTS or row.get("night")
    ]
    video_yes = [
        row
        for row in visual_yes
        if str(row.get("viewpoint") or "").lower() in VIDEO_HINTS or str(row.get("media_id") or "").startswith("video")
    ]
    flags: list[str] = []
    if text_hits["yes"] and text_hits["no_hits"]:
        flags.append("text_yes_and_no_phrases")
    if text_hits["no"] and visual_yes:
        flags.append("text_non_corner_vs_visual_corner")

    classification: CornerStatus = "UNKNOWN"
    confidence = 0.0
    source = "none"
    reason = "insufficient_listing_corner_evidence"
    frame_ids = [str(row["media_id"]) for row in visual_yes if row.get("media_id")]
    text_evidence = list(text_hits["yes_hits"] or text_hits["no_hits"])

    if text_hits["yes"] and not flags:
        classification = "YES"
        confidence = 0.90
        source = "text"
        reason = "explicit_unambiguous_corner_phrase"
        if visual_yes:
            confidence = min(0.97, 0.90 + 0.04 * min(len(visual_yes), 2))
            source = "text+visual"
            reason = "explicit_corner_text_and_visual_two_road_evidence"
    elif visual_yes and not text_hits["no"]:
        best = max(visual_yes, key=lambda row: float(row.get("visual_confidence") or 0.0))
        classification = "YES"
        confidence = float(best["visual_confidence"])
        source = "aerial" if best in aerial_yes or best.get("night") else "exterior"
        if video_yes and best in video_yes:
            source = "video"
        if aerial_yes:
            source = "aerial+exterior" if any(r not in aerial_yes for r in visual_yes) else "aerial"
        reason = str(best.get("reason") or "roads_visible_along_front_and_side_parcel_boundaries")
    elif text_hits["no"] and not visual_yes:
        classification = "NO"
        confidence = 0.93
        source = "text"
        reason = "explicit_positive_non_corner_phrase"
        text_evidence = list(text_hits["no_hits"])
    elif len(observations) == 1 and observations[0].get("strong_sides") and not visual_yes:
        reason = "only_one_visible_road_unknown_not_no"
        classification = "UNKNOWN"
        confidence = 0.0
        source = "visual_insufficient"

    if flags and classification == "YES":
        classification = "UNKNOWN"
        confidence = 0.0
        reason = "contradictory_listing_corner_evidence"
        source = "contradiction"

    high = classification == "YES" and confidence >= HIGH_YES_CONFIDENCE
    exceptional = (
        classification == "NO"
        and confidence >= EXCEPTIONAL_NO_CONFIDENCE
        and bool(text_hits["no"])
        and not visual_yes
    )
    return ListingCornerEvidence(
        classification=classification,
        confidence=round(confidence, 4),
        evidence_source=source,
        frame_ids=frame_ids,
        text_evidence=text_evidence,
        aerial_evidence=bool(aerial_yes) or (classification == "YES" and "aerial" in source),
        video_evidence=bool(video_yes),
        visual_reason=reason,
        contradiction_flags=flags,
        high_confidence=high,
        exceptional_non_corner=exceptional,
        positive_non_corner_evidence=bool(text_hits["no"]) and classification == "NO",
        frames=observations,
    )
