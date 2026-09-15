# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
