"""CoJ Property MapServer queries for official township parcels."""

from __future__ import annotations

import json
from typing import Any

import httpx

PROPERTY_MAPSERVER = "https://ags.joburg.org.za/server/rest/services/Property/MapServer"
REGISTERED_STANDS = 8
PROCLAIMED_TOWNSHIPS = 15
TOWNSHIP_SEARCH = 38
GATED_COMMUNITIES = 11
MAX_RECORDS = 1000

OFFICIAL_SUMMERSET_EXT = {
    2: "SUMMERSET EXT.2",
    6: "SUMMERSET EXT.6",
    13: "SUMMERSET EXT.13",
}


class CoJPropertyClient:
    def __init__(self, timeout_s: float = 60.0) -> None:
        self.timeout_s = timeout_s

    def query(
        self,
        layer: int,
        where: str,
        *,
        fields: str = "*",
        return_geometry: bool = False,
        out_sr: int = 4326,
        geometry: dict | None = None,
        spatial_rel: str = "esriSpatialRelIntersects",
    ) -> list[dict[str, Any]]:
        url = f"{PROPERTY_MAPSERVER}/{layer}/query"
        features: list[dict[str, Any]] = []
        offset = 0
        while True:
            params: dict[str, Any] = {
                "where": where,
                "outFields": fields,
                "returnGeometry": "true" if return_geometry else "false",
                "outSR": str(out_sr),
                "f": "json",
                "resultOffset": offset,
                "resultRecordCount": MAX_RECORDS,
            }
            if geometry is not None:
                params["geometry"] = json.dumps(geometry)
                params["geometryType"] = "esriGeometryPolygon"
                params["inSR"] = str(out_sr)
                params["spatialRel"] = spatial_rel
            with httpx.Client(timeout=self.timeout_s, follow_redirects=True) as client:
                response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
            if payload.get("error"):
                raise RuntimeError(payload["error"])
            batch = payload.get("features") or []
            features.extend(batch)
            if not payload.get("exceededTransferLimit") and len(batch) < MAX_RECORDS:
                break
            if not batch:
                break
            offset += len(batch)
        return features

    def township_record(self, official_name: str) -> dict[str, Any] | None:
        rows = self.query(
            TOWNSHIP_SEARCH,
            f"TOWN_NAME_DESC='{official_name}'",
            fields="TOWN_NAME_DESC,TS_ONLY_NAME,TS_EXT,STATUS_DESC,AREA_SQMT,TSG_ID",
            return_geometry=True,
        )
        if rows:
            return rows[0]
        rows = self.query(
            PROCLAIMED_TOWNSHIPS,
            f"TOWN_NAME_DESC='{official_name}'",
            fields="TOWN_NAME_DESC,TS_ONLY_NAME,TS_EXT,STATUS_DESC,AREA_SQMT,TSG_ID",
            return_geometry=True,
        )
        return rows[0] if rows else None

    def registered_stands(self, official_name: str) -> list[dict[str, Any]]:
        return self.query(
            REGISTERED_STANDS,
            f"TOWN_NAME_DESC='{official_name}'",
            fields=(
                "OBJECTID,SG_ID,STAND_NO,AREA_SQMT,TOWN_NAME_DESC,TS_ONLY_NAME,TS_EXT,"
                "STATUS_DESC,LAND_TYPE_NAME,PROPERTY_ID,ZONING,CAT_DESC,STREET_ADDRESS,"
                "STREET_NO,STREET_NAME,OWNER"
            ),
            return_geometry=True,
        )

    def gated_community(self, name: str) -> dict[str, Any] | None:
        rows = self.query(GATED_COMMUNITIES, f"NAME='{name}'", return_geometry=True)
        return rows[0] if rows else None


def geometry_extent(features: list[dict[str, Any]]) -> dict[str, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for feature in features:
        geometry = feature.get("geometry") or {}
        for ring in geometry.get("rings") or []:
            for x, y in ring:
                xs.append(float(x))
                ys.append(float(y))
    if not xs:
        return None
    return {
        "min_longitude": round(min(xs), 6),
        "max_longitude": round(max(xs), 6),
        "min_latitude": round(min(ys), 6),
        "max_latitude": round(max(ys), 6),
    }
