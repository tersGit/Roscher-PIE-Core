# W3-V full-universe geometry retrieval method

## Status

**NOT EXECUTED.** This document defines the precommitted, identity-blind
procedure that would have been applied to every frozen W1 crop. Execution was
stopped before crop access because the required frozen corpus is unavailable in
this worktree (see `VISUAL_GT_VERDICT.md`). No substitute imagery was fetched.

## Inputs and scope

- Target specification: the separately frozen `TARGET_GEOMETRY_PROFILE.md`.
- Universe: the 1,010 features enumerated by
  `data/estates/waterfall_country_estate/manifest.w1.json`.
- Required imagery: one 900 x 900, 135 m-context, 0.15 m/px W1 native15 crop
  per feature, referenced by that manifest.
- Parcel context: only each W1 feature's geometry and source properties.

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
