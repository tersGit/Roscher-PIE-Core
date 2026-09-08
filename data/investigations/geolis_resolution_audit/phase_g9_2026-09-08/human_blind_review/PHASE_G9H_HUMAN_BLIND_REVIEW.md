# Phase G9H human blind review

## Immutable blind-review record

Ters manually inspected all ten frozen Top-5 candidates across listings
`117539389` and `117255083` before ground truth. All 10 were inspected; no
true stand was known. Most candidates are visually not close matches.
Obvious contradictions include roof colour, pool shape, road/driveway
geometry, and a distinctive neighbouring high-pitched green zinc/metal roof
that was not captured or used.

This finding is an immutable pre-reveal human observation. It must remain
unchanged after any later authorized reveal and is not a claim about property
identity, address, erf number, owner, agent, or true stand.

## Scope and controls

- Evidence source: committed Phase G9 package frozen at
  `17e161ab3ce25c81003c2aa510ec5ab8e1ba2b88` only.
- Reviewed candidates: ranks 1-5 for each listing, as named in
  `PHASE_G9_TOP5_EXPLANATIONS.md`.
- The review did not fetch, search, reverse-geocode, identify, or otherwise
  recover a property or neighbourhood identity.
- This is diagnostic-only. It does not alter G9, the detector, PR #27,
  Shape v2, imagery, production scoring, or ranking.
- Roof colour may be a supporting negative contradiction only. Water colour
  is not a clue and was not used.

## Required protocol questions

1. **Were all frozen candidates inspected blind?** Yes. Ters inspected all
   10 Top-5 candidate views before ground truth; no true stand was known.
2. **Do most candidates look close enough to explain their ranks?** No. Most
   are visually not close matches despite their frozen production ranks.
3. **Which raw G9 clues were available on the listing side?** Exterior
   listing media retained roof appearance, pool/garden scenes, and
   driveway/garage scenes; the human review also observed the neighbour roof
   clue. The normal parser retained pool and scene-count evidence, not
   structured roof, neighbour, or road fields.
4. **Which raw G9 clues were available on the candidate side?** Native15
   candidate imagery, candidate pool contours, parcel geometry, and recorded
   road context were retained. They permit a blind visual comparison but not
   a completed structured roof, neighbour, or driveway comparison.
5. **Which clues need new extraction rather than new imagery?** Roof
   colour/material/pitch, neighbour fingerprint, road/driveway geometry,
   garage approach, and pool-to-house/pool-to-neighbour spatial relations.
   The committed raw evidence is sufficient to attempt extraction; no new
   acquisition is implied.
6. **What is the most damaging missing feature family?** The neighbourhood
   layout family: neighbouring-building fingerprint plus road/driveway and
   garage approach. It provides discriminative context that generic parcel
   and pool-presence signals do not.
7. **Is the frozen score pool-centric?** Yes. The top-five contributions
   show `shape_v2` plus `pool_presence` as the largest named visual components
   (for example, 0.2775 + 0.1400 for 117539389 rank 1 and 0.3196 + 0.1400 for
   117255083 rank 1). Pool evidence is informative but insufficiently
   discriminative without relational context.
8. **Was pool geometry itself fully compared?** No. G9 retained listing and
   candidate contours and Shape v2 metrics, but did not capture the complete
   contour family, curvature, rectangularity, aspect ratio, orientation, or
   pool-house relation as an explicit cross-side audit.
9. **At which stage did the observed evidence fail?** Primarily C/G:
   representation omitted first-class roof, neighbour, road, garage, and
   relational-pool fields, so retained evidence was ignored by spatial
   comparison and scoring. Pool has additional B/C/E/F risks documented in
   the pool audit.
10. **Does the evidence support a full property-and-neighbourhood layout
    fingerprint?** Yes, as a diagnostic extraction and comparison design.
    The evidence supports a composite fingerprint of property roof/pool,
    frontage/driveway/garage, and adjacent-neighbour features; it does not
    support identity recovery or a score change in this phase.

## Failure-stage legend

| Stage | Meaning | G9H assessment |
|---|---|---|
| A | Frame selection | Relevant listing frames were retained, but not selected for every diagnostic feature. |
| B | Feature extraction | Roof, neighbour, road, garage, and relational-pool extraction were absent. |
| C | Feature representation | No first-class cross-side fields represented these observations. |
| D | Candidate-side extraction | Candidate views existed, but equivalent structured extraction was absent. |
| E | Spatial comparison | No property-to-neighbourhood relational comparison ran. |
| F | Scoring/ranking | These contradictions could not penalize candidates; no change is made here. |
| G | Evidence existed but ignored | The retained visual/GIS evidence was not consumed as a diagnostic comparison feature. |

The candidate-level availability and stages are recorded in
`PHASE_G9H_VISUAL_FEATURE_AUDIT.csv`; detailed neighbour, road, and pool
audit definitions are in the companion records.
