# W3-V full-universe geometry retrieval method

## Status

**EXECUTED — `w3v-geometry-retrieval-v1`.** The authorized recovered corpus was
made available read-only after the initial unavailability record. The profile
hash was verified before candidate access and the procedure ran once across all
1,010 crops. No substitute imagery was fetched.

## Inputs and scope

- Target specification: the separately frozen `TARGET_GEOMETRY_PROFILE.md`.
- Universe: the 1,010 features enumerated by
  `data/estates/waterfall_country_estate/manifest.w1.json`.
- Required imagery: one 900 x 900, 135 m-context, 0.15 m/px W1 native15 crop
  per feature, referenced by that manifest.
- Parcel context: only each W1 feature's geometry and source properties.

Recovered source provenance (read-only, never copied, regenerated, modified,
or committed):

- `C:\Users\ters\copilot-worktrees\Roscher-PIE-Core\tersgit-probable-winner\data\visual_index\waterfall_country_estate_w1\_imagery_cache_native15`
  — 1,010 JPEGs, 223,719,172 bytes.
- `C:\Users\ters\copilot-worktrees\Roscher-PIE-Core\tersgit-probable-winner\data\cache\ags_native15\waterfall_country_estate_w1\manifest.json`
  — SHA256
  `b732dd96eddb3104cc69c7716d6e80498b39de08ec0b59b3f89f90aed99b377e`.

The procedure never reads an existing ranking, prediction, Top10 directory,
candidate score, stand identifier as a model feature, target identity, address,
or compass direction. Extension/stand fields are attached only after the
shortlist score order is written.

## Per-crop diagnostic measurements

All measures are computed for every crop using fixed, profile-derived
thresholds, not thresholds fitted to an identity:

1. **Water-like components:** HSV cyan/blue and low-saturation bright-water
   masks; connected-component area, rectangularity, aspect ratio, and edge
   alignment. The output state is `YES`, `NO`, or `UNKNOWN` (shadow, cover,
   blur, or insufficient resolution). `NO` never excludes a row.
2. **Building massing:** neutral/low-vegetation roof regions, rectilinear
   contour coverage, large component area, and flat/parapet-like edge density.
3. **House-pool relation:** distance and parallel/perpendicular edge relation
   between every plausible water component and dominant building component,
   retaining the best and second-best alternatives.
4. **Outdoor layout:** turf/vegetation fraction, contiguous open-space area,
   hardscape fraction, and compactness of the non-building rear-space pattern.
5. **Access/parcel context:** light hardscape components, candidate drive
   continuity to the crop border, and parcel polygon compactness/aspect. These
   are weak evidence because the target's exact driveway and parcel geometry
   are unknown.
6. **Texture/visibility:** local contrast, shadow proportion, foliage
   occlusion, and JPEG detail. Visibility downgrades confidence but does not
   turn absence into a negative claim.

## Fixed high-recall score

After min-max normalization within the full 1,010-row universe, the diagnostic
score is:

`0.30 water geometry + 0.24 building massing + 0.20 house-pool relation +`
`0.14 outdoor layout + 0.07 access/parcel context + 0.05 visual texture`.

When water is `UNKNOWN`, its contribution is set to the median water score
rather than zero and the uncertainty flag is retained. When water is `NO`, its
measured score remains in the weighted total. This makes a pool non-detection
non-eliminating and preserves high recall. Area is limited to the
access/parcel-context term and cannot exceed 0.02 of the total score.

## Freezes and review

The runner would write `FULL_UNIVERSE_SCORES.csv` with raw values, normalized
values, per-feature `YES/NO/UNKNOWN` states, visibility flags, score, and
reduction-bin counts for all 1,010 rows. Before opening a crop panel or joining
stand/extension labels, it would select ranks 1-30 by descending score with
stable tie-breaking solely on an opaque crop digest, write `SHORTLIST.csv`, and
write `SHORTLIST_FREEZE.sha256`.

Only then would a panel renderer add W1 crop, parcel overlay, and target
reference views. Forensic review would state supporting features,
contradictions, visibility/occlusion, and confidence without forcing a winner.
External GIS/current/historical aerial/Street View/public-building confirmation
would be required for a `HIGH` verdict. Existing rankings could be opened only
after an independent identity freeze; otherwise accuracy remains `UNLABELLED`.

## Execution record

The profile SHA256 was verified as
`56aca3c5d9d680a1a69dd19680d885fe38793c45900133f762267332d16d04bc`
immediately before candidate access. The 1,010-crop pass produced 2
`OBSERVED`, 1,008 `CONFLICT`, and 0 `UNKNOWN` water-geometry states. These
states diagnose the narrowly defined colour/shape component only; every row,
including every `CONFLICT`, remains ranked by the complete conjunction score.
