"""Estate Property Inventory v1 — cached estate-wide visual attributes.

Experimental layer only. Does not modify native15 acquisition, Object
Segmentation v1, FastSAM, Scoring v2, Hybrid Pool Geometry, viewpoint
gates, or production ranking.

Pool colour is not used. Classification consumes frozen OS v1 statuses
and parcel-mask notes only. UNKNOWN is never collapsed into NO.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Literal, Mapping, Sequence

from backend.gis.dataset_registry import CORRECT_CARLSWALD_NORTH
from backend.imagery.estate_tiles import (
    CACHE_PROFILES,
    DEFAULT_PROFILE_ID,
    PADDING_METRES,
    WEB_MERCATOR_RADIUS,
    cache_root_for,
    crop_dir_for,
)

INVENTORY_VERSION = "estate_property_inventory_v1"
INVENTORY_REVISION = "1.0.0"
SEGMENTATION_SOURCE_VERSION = "object_segmentation_v1"
ALGORITHM_VERSION = f"{INVENTORY_VERSION}.{INVENTORY_REVISION}+{SEGMENTATION_SOURCE_VERSION}"
SCHEMA_VERSION = f"{INVENTORY_VERSION}.{INVENTORY_REVISION}"

PoolStatus = Literal["YES", "NO", "UNKNOWN"]
OS_PRESENT = frozenset({"CONFIRMED", "PROBABLE"})
OS_BUILDING_OK = frozenset({"CONFIRMED", "PROBABLE"})

# Segmentation-quality guards — not pool ground truth. Fragmented / tiny
# roofs are a known OS v1 weakness and must not become a hard NO.
MIN_BUILDING_AREA_M2_FOR_NO = 180.0
MAX_BUILDING_MASSES_FOR_NO = 2

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INVENTORY_ROOT = REPO_ROOT / "data" / "estate_inventory"
DEFAULT_OS_DIR = (
    REPO_ROOT / "data" / "investigations" / "object_segmentation_v1" / "carlswald_north" / "json"
)
DEFAULT_GIS_PATH = REPO_ROOT / "data" / "gis" / f"{CORRECT_CARLSWALD_NORTH}.json"

EXTENSIBLE_ATTRIBUTES = (
    "roof_footprint",
    "driveway",
    "solar",
    "outbuildings",
    "building_orientation",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_stand(stand: str) -> str:
    return str(stand).replace("/", "_")


def canonical_dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def geometry_sha256(geometry: Mapping[str, Any] | None) -> str | None:
    if not geometry:
        return None
    rings = geometry.get("rings") or []
    rounded = [
        [[round(float(x), 7), round(float(y), 7)] for x, y in ring]
        for ring in rings
    ]
    return sha256_text(canonical_dumps(rounded))


def parcel_bbox(geometry: Mapping[str, Any] | None) -> tuple[float, float, float, float] | None:
    if not geometry:
        return None
    xs: list[float] = []
    ys: list[float] = []
    for ring in geometry.get("rings") or []:
        for x, y in ring:
            xs.append(float(x))
            ys.append(float(y))
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _mercator(lat: float, lon: float) -> tuple[float, float]:
    x = WEB_MERCATOR_RADIUS * math.radians(lon)
    y = WEB_MERCATOR_RADIUS * math.log(math.tan(math.pi / 4.0 + math.radians(lat) / 2.0))
    return x, y


def _inv_mercator(x: float, y: float) -> tuple[float, float]:
    lon = math.degrees(x / WEB_MERCATOR_RADIUS)
    lat = math.degrees(2.0 * math.atan(math.exp(y / WEB_MERCATOR_RADIUS)) - math.pi / 2.0)
    return lat, lon


def tile_grid_records(
    extent: Mapping[str, float],
    *,
    profile_id: str = DEFAULT_PROFILE_ID,
    year: int = 2023,
) -> list[dict[str, Any]]:
    """Same native15 grid as EstateTileIndex, without downloading or mutating cache."""
    profile = CACHE_PROFILES[profile_id]
    tile_metres = profile.tile_metres
    xmin, ymin = _mercator(extent["min_latitude"], extent["min_longitude"])
    xmax, ymax = _mercator(extent["max_latitude"], extent["max_longitude"])
    pad = tile_metres * 0.15
    xmin -= pad
    ymin -= pad
    xmax += pad
    ymax += pad
    cols = max(1, int(math.ceil((xmax - xmin) / tile_metres)))
    rows = max(1, int(math.ceil((ymax - ymin) / tile_metres)))
    tiles = []
    for row in range(rows):
        for col in range(cols):
            x0 = xmin + col * tile_metres
            y0 = ymin + row * tile_metres
            x1 = x0 + tile_metres
            y1 = y0 + tile_metres
            min_lat, min_lon = _inv_mercator(x0, y0)
            max_lat, max_lon = _inv_mercator(x1, y1)
            stem = f"tile_{year}_{profile.profile_id}_{row:02d}_{col:02d}"
            tiles.append(
                {
                    "tile_id": stem,
                    "row": row,
                    "col": col,
                    "min_lon": min_lon,
                    "min_lat": min_lat,
                    "max_lon": max_lon,
                    "max_lat": max_lat,
                }
            )
    return tiles


def _bboxes_intersect(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> bool:
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


def intersecting_tile_ids(
    geometry: Mapping[str, Any] | None,
    tiles: Sequence[Mapping[str, Any]],
    *,
    pad_metres: float = PADDING_METRES,
) -> list[str]:
    bbox = parcel_bbox(geometry)
    if bbox is None:
        return []
    pad = pad_metres / 111_320
    padded = (bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad)
    hits = []
    for tile in tiles:
        tile_bbox = (
            float(tile["min_lon"]),
            float(tile["min_lat"]),
            float(tile["max_lon"]),
            float(tile["max_lat"]),
        )
        if _bboxes_intersect(padded, tile_bbox):
            hits.append(str(tile["tile_id"]))
    return hits


def pass1_parcels(dataset: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Same GIS pass 1 as production ranking, then unique property_id last-wins."""
    selected = []
    for item in dataset.get("parcels") or []:
        if item.get("land_type") != "Erven":
            continue
        if item.get("class") in {"non_residential"}:
            continue
        if (item.get("area_sqm") or 0) >= 8000:
            continue
        if not item.get("geometry") or not item.get("stand_number"):
            continue
        if str(item["stand_number"]).startswith("RE/"):
            continue
        selected.append(item)
    unique: dict[int | str, dict[str, Any]] = {}
    for item in selected:
        unique[item.get("property_id") or item["stand_number"]] = item
    return [unique[key] for key in sorted(unique, key=lambda k: str(k))]


def parcel_id_of(parcel: Mapping[str, Any]) -> str:
    if parcel.get("property_id") is not None:
        return str(parcel["property_id"])
    return safe_stand(str(parcel.get("stand_number") or parcel.get("parcel_id") or ""))


def crop_path_for(
    estate_id: str,
    stand_number: str,
    *,
    profile_id: str = DEFAULT_PROFILE_ID,
    repo_root: Path | None = None,
) -> Path:
    return crop_dir_for(estate_id, profile_id, repo_root=repo_root) / f"{safe_stand(stand_number)}_ags_aerial.jpg"


def os_json_path_for(stand_number: str, os_dir: Path) -> Path:
    return Path(os_dir) / f"{safe_stand(stand_number)}.json"


@dataclass
class ImageryFingerprint:
    digest: str
    profile_id: str
    tile_ids: list[str]
    tile_hashes: dict[str, str]
    crop_hash: str | None
    geometry_sha256: str | None
    missing_tiles: list[str]
    crop_present: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "digest": self.digest,
            "profile_id": self.profile_id,
            "tile_ids": list(self.tile_ids),
            "tile_hashes": dict(self.tile_hashes),
            "crop_hash": self.crop_hash,
            "geometry_sha256": self.geometry_sha256,
            "missing_tiles": list(self.missing_tiles),
            "crop_present": self.crop_present,
        }


def compute_imagery_fingerprint(
    *,
    geometry: Mapping[str, Any] | None,
    crop_path: Path | None,
    tiles: Sequence[Mapping[str, Any]],
    tile_cache_root: Path | None,
    profile_id: str = DEFAULT_PROFILE_ID,
    year: int = 2023,
) -> ImageryFingerprint:
    tile_ids = intersecting_tile_ids(geometry, tiles)
    tile_hashes: dict[str, str] = {}
    missing: list[str] = []
    for tile_id in tile_ids:
        path = None if tile_cache_root is None else Path(tile_cache_root) / f"{tile_id}.jpg"
        digest = sha256_file(path) if path is not None else None
        if digest:
            tile_hashes[tile_id] = digest
        else:
            missing.append(tile_id)
    crop_hash = sha256_file(crop_path) if crop_path is not None else None
    geom_hash = geometry_sha256(geometry)
    payload = {
        "profile_id": profile_id,
        "year": year,
        "tile_ids": tile_ids,
        "tile_hashes": tile_hashes,
        "missing_tiles": missing,
        "crop_hash": crop_hash,
        "geometry_sha256": geom_hash,
    }
    return ImageryFingerprint(
        digest=sha256_text(canonical_dumps(payload)),
        profile_id=profile_id,
        tile_ids=tile_ids,
        tile_hashes=tile_hashes,
        crop_hash=crop_hash,
        geometry_sha256=geom_hash,
        missing_tiles=missing,
        crop_present=bool(crop_hash),
    )


@dataclass
class PoolClassification:
    pool_status: PoolStatus
    pool_confidence: float
    pool_count: int
    pool_centroid: list[float] | None
    pool_area_m2: float | None
    pool_bbox: list[float] | None
    normalized_pool_contour: list[list[float]] | None
    geometry_fingerprint: str | None
    diagnostic_flags: list[str]
    unknown_reason: str | None
    os_pool_status: str | None


def _contour_bbox(contour: Sequence[Sequence[float]]) -> list[float] | None:
    if not contour:
        return None
    xs = [float(pt[0]) for pt in contour]
    ys = [float(pt[1]) for pt in contour]
    return [round(min(xs), 4), round(min(ys), 4), round(max(xs), 4), round(max(ys), 4)]


def _centroid(pool: Mapping[str, Any], spatial: Mapping[str, Any]) -> list[float] | None:
    spatial_pool = spatial.get("pool") or {}
    parcel = spatial_pool.get("centroid_parcel")
    if parcel and len(parcel) >= 2:
        return [round(float(parcel[0]), 4), round(float(parcel[1]), 4)]
    geom = pool.get("geometry") or {}
    cx, cy = geom.get("centroid_x"), geom.get("centroid_y")
    if cx is None or cy is None:
        return None
    return [round(float(cx), 4), round(float(cy), 4)]


def classify_pool_from_os(os_payload: Mapping[str, Any] | None) -> PoolClassification:
    """Map frozen OS v1 pool output to inventory YES | NO | UNKNOWN.

    YES — OS CONFIRMED/PROBABLE in-parcel pool (not neighbour bleed).
    NO  — no in-parcel candidate after adequate segmentation. Never used
          for REJECTED (weak/confused OS evidence is not absence).
    UNKNOWN — weak evidence, neighbour/mask issues, or poor segmentation.
    """
    if not os_payload:
        return PoolClassification(
            pool_status="UNKNOWN",
            pool_confidence=0.0,
            pool_count=0,
            pool_centroid=None,
            pool_area_m2=None,
            pool_bbox=None,
            normalized_pool_contour=None,
            geometry_fingerprint=None,
            diagnostic_flags=["missing_os_payload"],
            unknown_reason="missing_os_payload",
            os_pool_status=None,
        )

    pool = os_payload.get("pool") or {}
    building = os_payload.get("building") or {}
    spatial = os_payload.get("spatial") or {}
    geom = pool.get("geometry") or {}
    notes = [str(item) for item in (pool.get("notes") or [])]
    os_status = pool.get("status")
    flags: list[str] = []
    if "partially_outside_parcel" in notes:
        flags.append("partially_outside_parcel")
    if "no_pool_candidate" in notes:
        flags.append("no_pool_candidate")
    if os_status == "REJECTED":
        flags.append("os_rejected")
        flags.extend(note for note in notes if note not in flags)

    contour = pool.get("contour") if geom.get("present") else None
    if contour:
        geom_fp = sha256_text(canonical_dumps({"contour": contour, "area_m2": geom.get("area_m2")}))[:16]
    else:
        geom_fp = None
    clip = pool.get("clip") or {}
    clip_pool = float(clip.get("pool") or 0.0)
    score = float(pool.get("score") or clip_pool or 0.0)
    centroid = _centroid(pool, spatial) if geom.get("present") else None
    area = geom.get("area_m2") if geom.get("present") else None
    bbox = _contour_bbox(contour) if contour else None

    neighbour_bleed = "partially_outside_parcel" in notes
    present = os_status in OS_PRESENT and bool(geom.get("present"))

    if present and not neighbour_bleed:
        flags.append("in_parcel_pool_detected")
        if os_status == "PROBABLE":
            flags.append("os_probable_not_confirmed")
        return PoolClassification(
            pool_status="YES",
            pool_confidence=round(max(score, clip_pool), 4),
            pool_count=1,
            pool_centroid=centroid,
            pool_area_m2=None if area is None else round(float(area), 2),
            pool_bbox=bbox,
            normalized_pool_contour=list(contour) if contour else None,
            geometry_fingerprint=geom_fp,
            diagnostic_flags=sorted(set(flags)),
            unknown_reason=None,
            os_pool_status=str(os_status),
        )

    if present and neighbour_bleed:
        return PoolClassification(
            pool_status="UNKNOWN",
            pool_confidence=round(min(max(score, clip_pool), 0.35), 4),
            pool_count=0,
            pool_centroid=None,
            pool_area_m2=None,
            pool_bbox=None,
            normalized_pool_contour=None,
            geometry_fingerprint=geom_fp,
            diagnostic_flags=sorted(set(flags + ["neighbour_or_mask_bleed"])),
            unknown_reason="pool_partially_outside_parcel",
            os_pool_status=str(os_status),
        )

    if os_status == "REJECTED":
        flags.append("rejected_is_not_absence")
        return PoolClassification(
            pool_status="UNKNOWN",
            pool_confidence=round(min(max(score, clip_pool), 0.35), 4),
            pool_count=0,
            pool_centroid=None,
            pool_area_m2=None,
            pool_bbox=None,
            normalized_pool_contour=None,
            geometry_fingerprint=None,
            diagnostic_flags=sorted(set(flags)),
            unknown_reason="os_rejected_weak_evidence_not_absence",
            os_pool_status="REJECTED",
        )

    building_geom = building.get("geometry") or {}
    building_area = float(building_geom.get("area_m2") or 0.0)
    masses = int(spatial.get("n_building_masses") or 0)
    building_ok = building.get("status") in OS_BUILDING_OK
    poor_segmentation = (
        not building_ok
        or masses > MAX_BUILDING_MASSES_FOR_NO
        or building_area < MIN_BUILDING_AREA_M2_FOR_NO
    )
    if poor_segmentation:
        flags.append("poor_segmentation")
        if not building_ok:
            flags.append("building_not_confirmed")
        if masses > MAX_BUILDING_MASSES_FOR_NO:
            flags.append("fragmented_building")
        if building_area < MIN_BUILDING_AREA_M2_FOR_NO:
            flags.append("undersized_building")

    if os_status == "UNKNOWN" and "no_pool_candidate" in notes and not poor_segmentation:
        flags.append("no_in_parcel_candidate_after_ok_os")
        return PoolClassification(
            pool_status="NO",
            pool_confidence=0.6,
            pool_count=0,
            pool_centroid=None,
            pool_area_m2=None,
            pool_bbox=None,
            normalized_pool_contour=None,
            geometry_fingerprint=None,
            diagnostic_flags=sorted(set(flags)),
            unknown_reason=None,
            os_pool_status="UNKNOWN",
        )

    reason = "inadequate_segmentation_or_imagery" if poor_segmentation else "os_unknown"
    if "no_pool_candidate" in notes and poor_segmentation:
        reason = "no_candidate_with_poor_segmentation"
    return PoolClassification(
        pool_status="UNKNOWN",
        pool_confidence=0.0,
        pool_count=0,
        pool_centroid=None,
        pool_area_m2=None,
        pool_bbox=None,
        normalized_pool_contour=None,
        geometry_fingerprint=None,
        diagnostic_flags=sorted(set(flags)),
        unknown_reason=reason,
        os_pool_status=None if os_status is None else str(os_status),
    )


def build_record(
    *,
    estate_id: str,
    parcel: Mapping[str, Any],
    fingerprint: ImageryFingerprint,
    classification: PoolClassification,
    scan_timestamp: str,
    reused: bool,
    segmentation_source: str,
    fastsam_invoked: bool,
    extra_flags: Sequence[str] = (),
) -> dict[str, Any]:
    flags = sorted(set(list(classification.diagnostic_flags) + list(extra_flags)))
    stand = str(parcel.get("stand_number") or "")
    return {
        "schema_version": SCHEMA_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "estate_id": estate_id,
        "parcel_id": parcel_id_of(parcel),
        "stand_number": stand,
        "township": parcel.get("township"),
        "property_id": parcel.get("property_id"),
        "parcel_geometry_ref": {
            "dataset_id": estate_id,
            "property_id": parcel.get("property_id"),
            "stand_number": stand,
            "township": parcel.get("township"),
            "geometry_sha256": fingerprint.geometry_sha256,
        },
        "imagery_profile": fingerprint.profile_id,
        "imagery_version": fingerprint.digest,
        "tile_ids": fingerprint.tile_ids,
        "tile_hashes": fingerprint.tile_hashes,
        "crop_hash": fingerprint.crop_hash,
        "scan_timestamp": scan_timestamp,
        "pool_status": classification.pool_status,
        "pool_confidence": classification.pool_confidence,
        "pool_count": classification.pool_count,
        "pool_centroid": classification.pool_centroid,
        "pool_area_m2": classification.pool_area_m2,
        "pool_bbox": classification.pool_bbox,
        "normalized_pool_contour": classification.normalized_pool_contour,
        "geometry_fingerprint": classification.geometry_fingerprint,
        "segmentation_source": segmentation_source,
        "os_pool_status": classification.os_pool_status,
        "diagnostic_flags": flags,
        "unknown_reason": classification.unknown_reason,
        "reused": bool(reused),
        "fastsam_invoked": bool(fastsam_invoked),
        "extensible_attributes": {name: None for name in EXTENSIBLE_ATTRIBUTES},
    }


@dataclass
class ScanStats:
    parcels_total: int = 0
    parcels_reused: int = 0
    parcels_rescanned: int = 0
    parcels_reclassified: int = 0
    fastsam_runs: int = 0
    changed_tiles: list[str] = field(default_factory=list)
    unchanged_tiles: list[str] = field(default_factory=list)
    runtime_s: float = 0.0
    yes: int = 0
    no: int = 0
    unknown: int = 0

    def to_dict(self) -> dict[str, Any]:
        total = max(self.parcels_total, 1)
        return {
            "parcels_total": self.parcels_total,
            "parcels_reused": self.parcels_reused,
            "parcels_rescanned": self.parcels_rescanned,
            "parcels_reclassified": self.parcels_reclassified,
            "fastsam_runs": self.fastsam_runs,
            "changed_tiles": self.changed_tiles,
            "unchanged_tiles": self.unchanged_tiles,
            "runtime_s": round(self.runtime_s, 3),
            "yes": self.yes,
            "no": self.no,
            "unknown": self.unknown,
            "yes_pct": round(100.0 * self.yes / total, 2),
            "no_pct": round(100.0 * self.no / total, 2),
            "unknown_pct": round(100.0 * self.unknown / total, 2),
        }


class EstateInventoryStore:
    def __init__(self, estate_id: str, root: Path | None = None) -> None:
        self.estate_id = estate_id
        self.dir = Path(root) if root is not None else DEFAULT_INVENTORY_ROOT / estate_id
        self.current_path = self.dir / "current.jsonl"
        self.history_path = self.dir / "history.jsonl"
        self.manifest_path = self.dir / "manifest.json"

    def ensure(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)

    def load_current(self) -> dict[str, dict[str, Any]]:
        if not self.current_path.is_file():
            return {}
        records = {}
        for line in self.current_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            records[str(row["parcel_id"])] = row
        return records

    def load_history(self, parcel_id: str | None = None) -> list[dict[str, Any]]:
        if not self.history_path.is_file():
            return []
        rows = []
        for line in self.history_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if parcel_id is None or str(row.get("parcel_id")) == str(parcel_id):
                rows.append(row)
        return rows

    def write_current(self, records: Mapping[str, Mapping[str, Any]]) -> None:
        self.ensure()
        lines = [
            canonical_dumps(records[key])
            for key in sorted(records, key=lambda item: str(item))
        ]
        tmp = self.current_path.with_suffix(".jsonl.tmp")
        tmp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        tmp.replace(self.current_path)

    def append_history(self, record: Mapping[str, Any]) -> None:
        self.ensure()
        with self.history_path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_dumps(record) + "\n")

    def write_manifest(self, payload: Mapping[str, Any]) -> None:
        self.ensure()
        self.manifest_path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_os_payload(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_crop_bgr(path: Path):
    import cv2

    image = cv2.imread(str(path))
    return image


def _default_segment(bgr, stand_number: str, geometry: Mapping[str, Any]) -> dict[str, Any]:
    from backend.vision.object_segmentation import objects_to_json, segment_parcel_bgr

    return objects_to_json(segment_parcel_bgr(bgr, stand_number=stand_number, geometry=dict(geometry)))


def _os_source_hash(payload: Mapping[str, Any] | None) -> str | None:
    if not payload:
        return None
    pool = payload.get("pool") or {}
    return sha256_text(
        canonical_dumps(
            {
                "version": payload.get("version"),
                "status": pool.get("status"),
                "score": pool.get("score"),
                "notes": pool.get("notes"),
                "area_m2": (pool.get("geometry") or {}).get("area_m2"),
                "contour": pool.get("contour"),
            }
        )
    )


def _tile_change_sets(
    previous: Mapping[str, Mapping[str, Any]],
    fingerprints: Mapping[str, ImageryFingerprint],
    all_tile_ids: Sequence[str],
) -> tuple[list[str], list[str]]:
    prev_hashes: dict[str, set[str]] = {}
    new_hashes: dict[str, set[str]] = {}
    for record in previous.values():
        for tile_id, digest in (record.get("tile_hashes") or {}).items():
            prev_hashes.setdefault(str(tile_id), set()).add(str(digest))
        for tile_id in record.get("tile_ids") or []:
            prev_hashes.setdefault(str(tile_id), set())
    for fingerprint in fingerprints.values():
        for tile_id, digest in fingerprint.tile_hashes.items():
            new_hashes.setdefault(str(tile_id), set()).add(digest)
        for tile_id in fingerprint.tile_ids:
            new_hashes.setdefault(str(tile_id), set())
    changed = []
    unchanged = []
    for tile_id in all_tile_ids:
        before = prev_hashes.get(tile_id, set())
        after = new_hashes.get(tile_id, set())
        if before != after:
            changed.append(tile_id)
        else:
            unchanged.append(tile_id)
    return changed, unchanged


SegmentFn = Callable[[Any, str, Mapping[str, Any]], Mapping[str, Any]]


def scan_estate_inventory(
    *,
    estate_id: str,
    dataset: Mapping[str, Any],
    store: EstateInventoryStore | None = None,
    os_dir: Path | None = None,
    repo_root: Path | None = None,
    profile_id: str = DEFAULT_PROFILE_ID,
    year: int = 2023,
    scan_timestamp: str | None = None,
    segment_fn: SegmentFn | None = None,
    allow_fastsam: bool = True,
) -> tuple[dict[str, dict[str, Any]], ScanStats]:
    """Build or refresh inventory. Reuses records when imagery + algorithm match."""
    started = time.perf_counter()
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    store = store or EstateInventoryStore(estate_id, root=root / "data" / "estate_inventory" / estate_id)
    os_dir = Path(os_dir) if os_dir is not None else DEFAULT_OS_DIR
    parcels = pass1_parcels(dataset)
    extent = dataset.get("extent") or dataset.get("gated_carlswald_north_estate_extent") or {}
    tiles = tile_grid_records(extent, profile_id=profile_id, year=year)
    tile_cache = cache_root_for(estate_id, profile_id, repo_root=root)
    previous = store.load_current()
    timestamp = scan_timestamp or utc_now()
    fingerprints: dict[str, ImageryFingerprint] = {}
    current: dict[str, dict[str, Any]] = {}
    stats = ScanStats(parcels_total=len(parcels))

    for parcel in parcels:
        pid = parcel_id_of(parcel)
        crop = crop_path_for(estate_id, str(parcel["stand_number"]), profile_id=profile_id, repo_root=root)
        fingerprints[pid] = compute_imagery_fingerprint(
            geometry=parcel.get("geometry"),
            crop_path=crop,
            tiles=tiles,
            tile_cache_root=tile_cache,
            profile_id=profile_id,
            year=year,
        )

    all_tile_ids = sorted({tile["tile_id"] for tile in tiles})
    if previous:
        stats.changed_tiles, stats.unchanged_tiles = _tile_change_sets(previous, fingerprints, all_tile_ids)
    else:
        stats.changed_tiles = []
        stats.unchanged_tiles = list(all_tile_ids)

    for parcel in parcels:
        pid = parcel_id_of(parcel)
        stand = str(parcel["stand_number"])
        fingerprint = fingerprints[pid]
        existing = previous.get(pid)
        imagery_same = bool(existing) and existing.get("imagery_version") == fingerprint.digest
        algo_same = bool(existing) and existing.get("algorithm_version") == ALGORITHM_VERSION
        os_path = os_json_path_for(stand, os_dir)
        os_payload = _load_os_payload(os_path)
        os_hash = _os_source_hash(os_payload)
        os_same = bool(existing) and existing.get("os_source_hash") == os_hash

        if existing and imagery_same and algo_same and (os_hash is None or os_same):
            current[pid] = existing
            stats.parcels_reused += 1
            continue

        extra_flags: list[str] = []
        fastsam_invoked = False
        segmentation_source = SEGMENTATION_SOURCE_VERSION
        crop = crop_path_for(estate_id, stand, profile_id=profile_id, repo_root=root)
        need_segment = allow_fastsam and crop.is_file() and (not imagery_same or os_payload is None)

        if need_segment:
            if segment_fn is not None:
                os_payload = dict(segment_fn(None, stand, parcel.get("geometry") or {}))
                fastsam_invoked = True
                stats.fastsam_runs += 1
                segmentation_source = str(os_payload.get("version") or SEGMENTATION_SOURCE_VERSION)
            else:
                bgr = _load_crop_bgr(crop)
                if bgr is None:
                    extra_flags.append("crop_unreadable")
                    os_payload = None
                    segmentation_source = "unavailable"
                else:
                    os_payload = dict(_default_segment(bgr, stand, parcel.get("geometry") or {}))
                    fastsam_invoked = True
                    stats.fastsam_runs += 1
                    segmentation_source = str(os_payload.get("version") or SEGMENTATION_SOURCE_VERSION)
        elif os_payload is not None:
            segmentation_source = str(os_payload.get("version") or SEGMENTATION_SOURCE_VERSION)
            extra_flags.append("reused_os_v1_json")
        else:
            extra_flags.append("missing_crop_and_os_json")
            segmentation_source = "unavailable"

        if existing and imagery_same and not fastsam_invoked:
            stats.parcels_reclassified += 1
        else:
            stats.parcels_rescanned += 1

        classification = classify_pool_from_os(os_payload)
        record = build_record(
            estate_id=estate_id,
            parcel=parcel,
            fingerprint=fingerprint,
            classification=classification,
            scan_timestamp=timestamp if not (existing and imagery_same) else str(existing.get("scan_timestamp") or timestamp),
            reused=False,
            segmentation_source=segmentation_source,
            fastsam_invoked=fastsam_invoked,
            extra_flags=extra_flags,
        )
        record["os_source_hash"] = os_hash if not fastsam_invoked else _os_source_hash(os_payload)
        current[pid] = record
        if existing:
            prior_obs = {k: existing.get(k) for k in ("imagery_version", "pool_status", "scan_timestamp", "algorithm_version")}
            new_obs = {k: record.get(k) for k in ("imagery_version", "pool_status", "scan_timestamp", "algorithm_version")}
            if prior_obs != new_obs:
                store.append_history({**existing, "history_event": "superseded"})
                store.append_history({**record, "history_event": "current"})
        else:
            store.append_history({**record, "history_event": "current"})

    for record in current.values():
        status = record.get("pool_status")
        if status == "YES":
            stats.yes += 1
        elif status == "NO":
            stats.no += 1
        else:
            stats.unknown += 1

    store.write_current(current)
    stats.runtime_s = time.perf_counter() - started
    store.write_manifest(
        {
            "schema_version": SCHEMA_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "estate_id": estate_id,
            "imagery_profile": profile_id,
            "segmentation_source": SEGMENTATION_SOURCE_VERSION,
            "parcel_count": stats.parcels_total,
            "scan_timestamp": timestamp,
            "stats": stats.to_dict(),
        }
    )
    return current, stats


def load_inventory_records(estate_id: str, root: Path | None = None) -> list[dict[str, Any]]:
    store = EstateInventoryStore(estate_id, root=root)
    current = store.load_current()
    return [current[key] for key in sorted(current)]


def status_counts(records: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"YES": 0, "NO": 0, "UNKNOWN": 0}
    for record in records:
        status = str(record.get("pool_status") or "UNKNOWN")
        if status not in counts:
            status = "UNKNOWN"
        counts[status] += 1
    return counts
