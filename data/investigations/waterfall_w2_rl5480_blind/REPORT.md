# Waterfall W2 blind ranking freeze - RL5480

## Blind firewall

- W1 immutable evidence commit: `e86b156`; GeoJSON SHA256: `6a375bf542bcff28c6a3ee862f9e0c3c9a5395d0497b4159027c40b75cf7be3a`.
- W1 candidate universe: exactly 1,010 parcels from extensions 19, 38, 39, 40, 43, and 105.
- Listing-only evidence commit: `6b440905c55d3b725351ee9a90a83d51aee3338c`.
- No candidate crop was accessed before that commit. No address, coordinate, agent, portal, price, reverse-image, duplicate-listing, or ground-truth recovery was used.

## Listing extraction and visual freeze

- Normal rendered gallery: 48 original images, each recorded with source order, URL, dimensions, and SHA256 in `listing_media_manifest.json`.
- Standard rendered embeds/assets: **NO VIDEO FOUND**.
- Listing visual-freeze SHA256: `2e354ad931df2fdfa7dd509f73a0551ee6e3d934cb265dcbe4e47e8ef7fba2b4`.

| Feature | State | Confidence | Expected aerial visibility | Listing-only observation |
| --- | --- | ---: | --- | --- |
| pool | YES | 0.99 | HIGH | A private in-ground pool is repeatedly visible behind the house. |
| pool_shape | YES | 0.84 | HIGH | Multiple elevated oblique views support a broad curvilinear/kidney-like pool outline; exact nadir contour remains uncertain. |
| house_roof_structure | YES | 0.78 | MEDIUM | Large two-storey residence with multi-plane pitched tiled roof and rear covered entertainment patio. |
| driveway_garage | YES | 0.9 | MEDIUM | Paved front approach leads directly to three adjacent automated garage doors; complete driveway extent is not visible. |
| boundary_street | YES | 0.7 | LOW | Brick perimeter wall, mature landscaped front garden, and broad paved street-side approach are visible; full street geometry is incomplete. |
| neighbours | UNKNOWN | 0.2 | MEDIUM | Listing views do not provide sufficient unobscured neighbouring-parcel evidence. |
| landscape_open_space | YES | 0.68 | MEDIUM | Established garden and lawn are visible. The green-belt setting is retained as a listing claim, not identity evidence. |
| aerial_visible_features | YES | 0.7 | HIGH | Pool, large roof mass, rear patio/deck, and substantial garden should be aerially discernible. |

The 1,035 m2 land size is weak supporting evidence only (experimental contribution 5%). The green-belt phrase is retained as listing evidence and never used as identity.

## Candidate ranking

- All 1,010 W1 crops were generated from the W1-declared 2023 native15 source after the visual freeze.
- Generic existing PIE colour seed, roof seed, contour descriptor, and Scoring v2-derived experimental weights were applied uniformly. No candidate was eliminated for pool NO/UNKNOWN; this run emits YES or UNKNOWN only.
- Greenbelt context is independently marked `possibly` or `unknown` from W1 aerial context only; it is not a hard gate.
- Ranking freeze SHA256: `93b488bef582d5a97f5dc034cca4eded86520912ac6cebec28620cbd149b4a0e`.

### Top 10

| Rank | Stand | Ext | Property ID | Total | Pool / geometry | Roof | Driveway | Greenbelt | Area m2 | Missing / unknown |
| ---: | --- | ---: | --- | ---: | --- | --- | --- | --- | ---: | --- |
| 1 | 972 | 19 | 2033220 | 0.7878 | YES / irregular | YES | YES | unknown | 1046.0 | neighbour |
| 2 | 838 | 19 | 2032570 | 0.7829 | YES / irregular | YES | YES | unknown | 1185.0 | neighbour |
| 3 | 1018 | 19 | 2033278 | 0.7771 | YES / irregular | YES | YES | unknown | 1050.0 | neighbour |
| 4 | 906 | 19 | 2033195 | 0.7763 | YES / irregular | YES | YES | unknown | 1037.0 | neighbour |
| 5 | 3269 | 105 | 2083833 | 0.7751 | YES / irregular | YES | YES | unknown | 1053.0 | neighbour |
| 6 | 1002 | 19 | 2033255 | 0.7749 | YES / irregular | YES | YES | unknown | 1125.0 | neighbour |
| 7 | 3323 | 105 | 2083663 | 0.7739 | YES / irregular | YES | YES | unknown | 1114.0 | neighbour |
| 8 | 1169 | 19 | 2032908 | 0.7739 | YES / irregular | YES | YES | unknown | 1050.0 | neighbour |
| 9 | 897 | 19 | 2033185 | 0.7734 | YES / irregular | YES | YES | unknown | 1150.0 | neighbour |
| 10 | 1081 | 19 | 2033104 | 0.7727 | YES / irregular | YES | YES | unknown | 1014.0 | neighbour |

## Review package

- `ranking_full.csv` and `ranking_full.json`: complete 1,010-parcel ranking.
- `ranking_review.json`: Top 50, Top 20, Top 10, and Top 5.
- `top5_contact_sheet.jpg`: native15 candidate crops with parcel boundaries and score overlays plus three listing exterior references.

**GROUND TRUTH RECOVERY = NOT STARTED**
