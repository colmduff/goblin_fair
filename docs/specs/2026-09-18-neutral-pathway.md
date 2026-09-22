# goblin_fair — neutrality tools

- **Date:** 2026-09-18
- **Author:** Colm Duffy
- **Status:** approved, implemented on `feat/v0.1`
- **Builds on:** `2026-09-16-leave-one-out.md`

## Why

goblin_fair could say how much warming an entity causes. It could not answer the
question people actually ask: *what would this entity have to emit to stop adding
warming?* That is needed for any temperature-neutrality target — for Ireland, for the EU,
for a sector or a farm. The first real use is the EU's interest in temperature neutrality
for biogenic methane, where the question is how much methane that target allows. Nothing
in the design is specific to that case.

## What was added

### 1. Stream labels (optional)

A column may carry a label after a colon: `CH4:biogenic`, `CH4:fossil`. Labels are free
text. FaIR has one CH4, so every label of a gas is summed before it reaches the model; a
label exists only so one stream can be reported or solved for on its own. A plain `CH4`
column behaves exactly as before, and a gas must be labelled everywhere or nowhere.

Splitting is accounting, not physics. Contributions of separate streams do not add up
exactly to the contribution of the whole, because methane's lifetime depends on how much
methane is in the air.

### 2. When does a pathway become neutral? (`ContributionResult`)

- `warming_rate(window=10)`: how fast the contribution is changing, K per year, per
  member. Trailing, so it only uses years that have already happened.
- `neutrality(from_year, rule, tolerance, window)`: the first year from which the entity
  adds no more warming, per member, with `share_reached` and `by_share(0.5 / 0.9)`.
  Rules: `"peak"` (never rises again) and `"hold"` (never again above the `from_year`
  level). Both must hold for every later year, so a relapse does not count.

### 3. What pathway gets there? (`neutral_pathway`)

`gf.neutral_pathway(emissions, solve="CH4", from_year=2025, by_year=None, ...)` returns
the smallest steady yearly cut that keeps the entity's warming from ending up above its
`from_year` level, plus the pathway that implies and the gap from the pathway given.

Decisions worth recording:

- **A steady % cut, not a free path per year.** A year-by-year solve is ill-conditioned:
  methane's warming peaks about six years after the emission, so the solver swings up and
  down chasing it and produces a saw-tooth nobody can act on. One rate is also the answer
  people ask for.
- **`from_year` is the first year of action**, and the level cut from is that year's
  emissions. Otherwise the target is unreachable: the emissions of `from_year` already
  set the next year's warming.
- **`by_year` is when the line must be met** (default: the last emission year). Years in
  between are the transition. Without this, the rule "never rise again, from tomorrow"
  forces an immediate collapse to near-zero emissions, which is not what neutrality means.
- **The search runs FaIR** at different rates and halves the range (7 steps ≈ 0.04 %/yr).
  An earlier version used a linear "kernel" shortcut; it was dropped because its error
  (about 4 % of the pinned warming) was the same size as the quantity being resolved.
  Every number reported now comes from a real run.
- **Judged per ensemble member.** Each member has its own required rate, read off the
  runs that bracket it, so the result carries a range (p5 / p50 / p95) and
  `share_neutral`: the share of members for which the reported pathway really works.
  Statistics are taken per member and then summarised, never from a median curve.

## Tests

Fast: labelled streams; `warming_rate`; `neutrality` rules, tolerance and `by_share`;
the pathway maths (`decline_path`, `overshoot`, `solve_rate`) on made-up curves.
Slow (real FaIR): a steady emitter must cut slowly, not stop; the solved pathway really
does hold warming flat when put back through the public API; a gentler cut fails; an
earlier `by_year` demands a faster cut; solving one stream leaves the others untouched;
two labelled streams equal one combined column exactly.

## Not done yet

- Whole-entity neutrality across gases (CO2 and N2O criteria, and the interaction
  residual between streams).
- Loaders for real inventories and projections (Ireland, EU).
- A helper to run several pathways or backgrounds in one call.
