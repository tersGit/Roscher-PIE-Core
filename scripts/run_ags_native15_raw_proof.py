#!/usr/bin/env python3
"""Write a labelled raw Council/AGS native15 proof panel for one Carlswald erf.

Isolated diagnostic. Does not modify OS v1, FastSAM, Scoring v2, Hybrid geometry,
native15 production cache, ranking, inventory current.jsonl, or the listing pool gate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.gis.estate_ags_matching.ags_native15_raw_proof import PREFERRED_STAND, run_proof


def main() -> int:
    payload = run_proof(PREFERRED_STAND)
    print(
        json.dumps(
            {
                "stand_number": payload["stand_number"],
                "inventory_pool_status": payload["inventory_pool_status"],
                "os_pool_status": payload["os_pool_status"],
                "source_tile_id": payload["source_tile_id"],
                "crop_pixel_dimensions": payload["crop_pixel_dimensions"],
                "os_v1_crop_wh": payload["os_v1_crop_wh"],
                "crop_matches_os_v1_wh": payload["crop_matches_os_v1_wh"],
                "native_metres_per_pixel": payload["native_metres_per_pixel"],
                "requested_metres_per_pixel": payload["requested_metres_per_pixel"],
                "resampled_from_native": payload["resampled_from_native"],
                "google_bing_or_other_satellite_used": payload["google_bing_or_other_satellite_used"],
                "raw_crop_path": payload["raw_crop_path"],
                "proof_panel_path": payload["proof_panel_path"],
                "object_pixel_dimensions": {
                    kind: {
                        k: v.get(k)
                        for k in ("approx_width_px", "approx_length_px", "os_area_px", "os_area_m2")
                    }
                    for kind, v in (payload.get("object_pixel_dimensions") or {}).items()
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
