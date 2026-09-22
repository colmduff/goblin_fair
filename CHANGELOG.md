# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- `neutral_pathway` no longer crashes when growth is allowed. The search may try growth so
  fast that the entity would out-emit the whole world, which leave-one-out rejects. Such a
  rate now counts as "not neutral" and the search carries on. The same error at a non-growth
  rate is still raised, because it means bad input.
- `neutral_pathway` now measures every member's rate on both sides. When 0 % already works
  for the median member, the search used to try only growth, so members needing a cut were
  reported at 0 %. It now adds runs until each member has a rate that works and one that does
  not. `verification["rates_tried"]` lists them.
  A member whose next rate out was impossible used to come out as NaN; it now gets the
  gentlest rate known to work.

### Added
- `gf.neutral_pathway()`: the smallest steady yearly cut that stops an entity adding
  warming, with the pathway it implies, the gap from the pathway you gave, and a range
  across ensemble members. The search runs FaIR itself, so every number comes from a
  real run (spec: docs/specs/2026-09-18-neutral-pathway.md).
- `ContributionResult.warming_rate()` and `.neutrality()`: how fast an entity's warming
  is changing, and the first year it stops rising ("peak" or "hold" rules), per member.
- Optional stream labels in emissions columns (`CH4:biogenic`, `CH4:fossil`). FaIR has
  one CH4, so labels are summed before the run; they exist to report or solve for one
  stream on its own. `metadata["streams"]` records them.

### Changed
- `temperature_contribution` now uses **leave-one-out** attribution by default
  (`method="leave_one_out"`): the SSP background as it is, minus the SSP background
  without the emissions. The v0.1 behaviour is available as `method="add"`.
- `ContributionResult` fields `background_temperature` / `perturbed_temperature` are
  now `with_temperature` / `without_temperature`, plus a `method` field.
  `background_warming()` always describes the unmodified SSP run.

### Added
- A `ValueError` when the emissions would leave negative global CH4 or N2O emissions.
- `metadata["method"]`.
- Slow tests for leave-one-out, CO2_AFOLU-only and N2O-only runs, and explicit member lists.

## [0.1.0] - 2026-09-15

### Added
- `temperature_contribution()`: the marginal global surface temperature contribution of
  CO2 (total, or fossil/AFOLU), CH4 and N2O emissions. It uses FaIR 2.2.4 with the
  calibrated, constrained v1.4.1 ensemble (841 members) on an RCMIP v5.1.0 SSP background.
- `ContributionResult` with `summary()`, `ensemble`, `background_warming()`, `plot()`
  and `metadata`.
- `list_backgrounds()`: the eight SSP background scenarios.
- Input validation: unit conversion (t/kt/Mt/Gt), rejection of CO2-equivalent input,
  and checks on years and values.
- Bundled model data with full provenance (`src/goblin_fair/data/DATA_SOURCES.md`) and a
  deterministic rebuild script (`scripts/build_data.py`).
- pytest suite: fast unit tests, slow real-FaIR tests, and a network cross-check against
  `fair`'s own RCMIP loader.
- Performance: all 841 members, 1750-2100, in about 18 s on the development machine.
