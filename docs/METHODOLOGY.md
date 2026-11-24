# Methodology

What the app computes, what each number means, and what is **not** established yet. The numbers in
`backend/config/states/telangana.yaml` are the single source of truth; this page explains them.

## What the app can and cannot say

It estimates **groundwater potential**: how favourable the ground around a location looks for storing and
yielding water, judged from published geology, soil, terrain, rainfall and monitoring-well data.

It does **not** say whether water exists at a spot, how much a borewell will yield, how deep to drill, or what the
water quality is. Only drilling, preceded by a site survey, shows that. Every result, every PDF and the home page
say so, and the map legend and wording keep "potential" and "confirmed water" apart.

## 1. Regional index (the coloured map)

A weighted overlay, the standard approach in published "groundwater potential zone" (GWPZ) studies.

```
index = sum(weight_i x score_i) / sum(weight_i)        over the factors that apply and have data
```

Each factor value is turned into a 0-100 score: categorical factors (lithology, aquifer, soil) by a lookup table,
numeric factors by linear interpolation between the breakpoints in the config (values beyond the ends take the end
score).

| Factor | Weight | Input |
|---|---|---|
| Geological formation (lithology) | 0.20 | GSI geology polygon |
| Aquifer type | 0.10 | CGWB aquifer polygon |
| Soil texture | 0.08 | soil polygon |
| Land slope | 0.12 | DEM-derived, degrees |
| Drainage density | 0.10 | DEM or stream map, km/km² |
| Lineament density | 0.10 | lineament map, km/km² (not applied on alluvium) |
| Normal annual rainfall | 0.10 | IMD gridded, mm |
| Topographic position | 0.05 | DEM-derived, m above/below surroundings |
| Pre-monsoon depth to water | 0.15 | interpolated from monitoring wells, m below ground |

Rules that keep it honest:

- **Missing factors are dropped, never guessed.** The remaining weights are re-normalised, and the share of
  applicable weight that had data is the *coverage*.
- If lithology is missing, or coverage is below 0.55, the result is **"insufficient data"** (grey) with no class and
  no confidence figure.
- Lineaments are not applied on alluvium, where flow is through pores rather than fractures.
- The map layer and the report use the same function (`regional_for_point`), so the colour on the map and the class in
  the report cannot disagree.

Classes: **high** at 65 and above (blue), **moderate** from 53 (green), **low** from 42 (yellow), **very low**
below that (red), **insufficient data** (grey). The colours are fixed by the product specification and are used for
nothing else in the interface.

## 2. Local evidence

When historical borewell records or geophysical surveys exist near the point they adjust the regional index. The
regional index acts as a prior worth `prior_strength = 3` pseudo-records; each nearby record adds one observation:

```
final = (3 x regional + n_eff x local_mean) / (3 + n_eff)
```

- Borewell records within 3 km count, each with weight `1 / (1 + distance_km)`; records with a location accuracy
  worse than 500 m count half. Outcomes map to scores: dry 0, low 35, moderate 65, good 90.
- A geophysical survey within 2 km counts with weight `2 / (1 + distance / 0.5 km)` and a score from its
  interpreted suitability: good 85, moderate 55, poor 15.
- If the total weight `n_eff` is below 1, local evidence is ignored.
- With few records the result stays near the regional index; with many it follows what actually happened nearby.
- If at least 3 records disagree with the regional index by 30 points or more, the report says so.

## 3. Depths (feet, only where data supports it)

Two different depths are shown and never merged:

- **Depth to the water table** (pre-monsoon, with post-monsoon where available). From monitoring wells within 15 km:
  each well's median reading over the last 3 years, then an inverse-distance-weighted estimate (power 2). The range
  shown is the **spread between the nearby wells**, not a prediction interval for your plot. At least 2 wells with
  recent readings are needed; otherwise the figure is reported as unavailable. The trend is the median per-well slope
  of pre-monsoon readings over up to 12 years (at least 4 distinct years). **A positive trend means the water table is
  getting deeper, i.e. the water level is falling.**
- **Depth drilled in nearby productive borewells.** The 10th-90th percentile of depths of borewells with a moderate
  or good outcome within 5 km (else 10 km), rounded to 10 ft, only if there are **at least 5** such records. There is
  no model and no extrapolation: it is a summary of what people drilled nearby. Dry borewells are reported
  separately ("2 nearby borewells were dry, the deepest to 420 ft") because a deeper borewell is not a surer one.

If the records are not there, the field says "not available" and why.

## 4. Confidence

A number from 0 to 1, shown as low / medium / high. **It is not the probability of finding water.** It says how well
the class is supported by the data that actually exists.

| Component | Weight | Full marks when |
|---|---|---|
| Factor coverage | 0.30 | all applicable factors have data |
| Local support | 0.25 | the effective number of local records reaches 8 |
| Water-level support | 0.15 | at least 3 wells, the nearest within 5 km (half marks within 10 km) |
| Geophysics | 0.10 | a survey exists within 2 km |
| Recency | 0.10 | newest water-level reading is under 2 years old (older: 0.7, 0.4, then 0.2) |
| Consistency | 0.10 | local evidence agrees with the regional index |

Below 0.35 is low and from 0.65 is high. **High is impossible without at least 5 effective local records**; the
interface says when this cap applied.

## 5. Optional statistical model

A gradient-boosting classifier can be trained on real borewell records (`python -m scripts.train_model`) as a *second
opinion*. It is served only if it passes a gate: at least 500 records, a **spatial-block** cross-validated AUC of at
least 0.70 (5 km blocks, so it is tested on places it has not seen), and it was trained on the same data mode the API
runs in. It never changes the class or the score; if it disagrees with the index, the report says so and confidence
goes down. On the demonstration data its cross-validated AUC is about 0.6, so it is **correctly refused**. That is
by design and is not a bug to fix by tuning the demo data.

## 6. Before real people rely on this

The code is finished; the science is not. These are open and must be handled before the app is used for real
decisions:

1. **The scoring tables are priors, not fitted values.** Weights, class scores and breakpoints are expert-assigned in
   the style of published studies. They have **not** been checked against Telangana borewell outcomes. A
   hydrogeologist who works in the state must review every table.
2. **The class thresholds (65 / 53 / 42) are placeholders** tuned to the demonstration data. They must be re-chosen on
   the real distribution of index values.
3. **Some factors overlap.** Lithology and aquifer type describe much of the same rock; lineaments and drainage are
   correlated with slope. A weighted sum counts that information more than once. Reviewers should consider merging or
   down-weighting.
4. **Hard rock behaves differently.** In granite, gneiss and similar rock, yield follows fractures that vary over tens
   of metres. A regional index is a weak guide there, and the report says so. Much of Telangana is underlain by
   crystalline rock, so this affects a large part of the state.
5. **Records are biased.** Borewells are drilled where people expected water, dry ones are under-reported, owners
   deepen until they find water, and outcome classes are subjective. Treat the local evidence as indicative.
6. **Interpolated water levels are smooth; the ground is not.** A nearby well says little about a plot on the other
   side of a dyke.
7. **Telugu text** was written for this project and has not been reviewed by a native speaker with groundwater
   vocabulary. Have it reviewed before launch (`frontend/src/i18n/te.js`, `backend/app/i18n.py`, the state
   config labels).

## Calibration and validation

Do this with real data before publishing.

1. **Assemble the evaluation set.** Real borewell records with a recorded outcome and a trustworthy location. Set aside
   a share that is never used to tune anything. Split **by area** (spatial blocks), not at random, or the result is
   flattering because neighbouring borewells are alike.
2. **Check the ranking.** Compute the regional index at each record's location (using only the regional stage) and
   measure how well it separates productive from dry borewells (AUC). If it is near 0.5, the index is not informative
   in that area and the product should say so or not be shown there.
3. **Check the classes.** For each class, report the share of borewells that were productive, with sample sizes and
   uncertainty. The classes should be ordered (high above moderate above low above very low). Choose the class
   thresholds so that they are, and so that very-low / high mean something measurable.
4. **Check the weights.** Try dropping or re-weighting factors (and merging overlapping ones) and see what the
   validation says. Prefer simpler tables that hold up on held-out areas.
5. **Check hard rock and sedimentary areas separately.** An index that works on the sedimentary belt may be useless on the
   crystalline plateau.
6. **Check depth statements.** Compare the 10th-90th percentile range with held-out borewells: roughly 80% should fall inside.
7. **Re-run `scripts.compute_potential`** after changing the config, then re-check.
8. **Write down the result**, including where the method failed, and keep that page next to the app. Update the "limits"
   page text if the evidence changes what you can honestly claim.

## Reproducibility

Every response carries the method version (`gwpz-wo-1.0`), the data sources with their dates and licences, and the
generation time. Change the config and the version string together, so a report can always be tied to the exact tables
that produced it.
