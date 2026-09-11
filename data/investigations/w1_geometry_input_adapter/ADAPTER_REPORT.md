# W1 geometry input adapter

The authoritative source is frozen W1 GeoJSON from e86b156, SHA256 `6a375bf542bcff28c6a3ee862f9e0c3c9a5395d0497b4159027c40b75cf7be3a` (1,010 properties). Original W1 `_crop_tiles` code supplies the crop contract: a 900px square centred on its stored centroid in EPSG:3857, with 0.15 m/px and bounds centre +/-67.5 m. The crop filename is verified against that producer contract and extension; it is not treated as an independent property identifier.

The reported 81/637 discrepancy is not present in the frozen W5 artifact: its A/B candidate IDs map 272/272 and 365/365 to frozen W1 properties. The prior diagnostic instead marked all 637 inputs source-unavailable, so its partial join cannot be used as W1 mapping evidence.

Masks are deterministically rasterized on demand from frozen polygons and affine georeferences, including rings and clipping. No manual, imagery, or FastSAM boundaries are used.
