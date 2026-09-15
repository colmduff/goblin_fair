# goblin_fair v0.1 — design spec

- **Date:** 2026-09-15
- **Author:** Colm Duffy
- **Status:** approved design, pending implementation plan

## 1. Purpose

`goblin_fair` makes the FaIR simple climate model (`fair`, https://pypi.org/project/fair/)
easy to use and easy to understand for one question:

> *What global surface temperature change is caused by this set of emissions?*

FaIR v2 can already answer this, but it needs ~25 lines of setup (time axis, scenarios,
configs, species, allocation, filling emissions and forcing, overriding calibrated
parameters, initialising state) before the first run. `goblin_fair` hides that behind one
function and one result object, and documents where every number comes from.

### Project objectives

1. **(v0.1, this spec)** A simple workflow for the temperature impact of emissions.
2. *(later)* Take Irish emissions datasets and compute their temperature contribution.
3. *(later)* The same for the EU as a bloc, individual European countries, or any country.

v0.1 must be designed so objectives 2 and 3 are "produce an emissions DataFrame and call
the same function" — no API change.

## 2. Decisions made

| Question | Decision |
|---|---|
| Engine | **Wrap the official `fair` package** (pinned `fair==2.2.4`); no reimplementation. |
| Gases | **CO2, CH4, N2O** only. CO2 may be given as one total or split fossil/AFOLU. |
| Framing | **Marginal contribution against a global background scenario.** |
| Uncertainty | **Calibrated, constrained ensemble from day one** (841 members). |
| Calibration / data | **FaIR calibration v1.4.1** + **RCMIP v5.1.0 SSP** backgrounds. |
| API style | **Approach A:** one function returning one result object. |
| Data | **Bundled in the package**, with full provenance documentation and a rebuild script. |

Rejected alternatives, for the record:
- Own reimplementation — results drift from published FaIR; we would own the science.
- Standalone (emissions-only from pre-industrial) runs — ignores non-linearities
  (CO2 uptake saturation, CH4 lifetime), inappropriate for national attribution.
- Calibration v1.6.0 — newest, but ships no future scenarios and is not the peer-reviewed
  version; its author warns "the newest isn't always the best".
- The draft CMIP7 "extensions" scenarios shipped in FaIR's example — FaIR's authors advise
  against using them naively.
- Builder/Experiment class, YAML+CLI — more concepts than the use case needs.

## 3. Feasibility evidence (spike, 2026-09-15, throwaway code)

- FaIR 2.2.4, calibration v1.4.1, 841 members, 1750–2100, RCMIP `ssp245` background:
  **~11 s per run** on the dev machine.
- Background warming vs 1850–1900 (p5 / p50 / p95): 2022 0.98 / 1.25 / 1.47 °C;
  2050 1.49 / 1.89 / 2.33 °C; 2100 1.90 / 2.63 / 3.58 °C (AR6 SSP2-4.5 median ≈ 2.7 °C).
- Marginal test: +1 Gt CO2/yr from 2020–2100 on the draft `medium-extension` background
  gave +26.7 mK in 2100 (p5 18.1, p95 37.4) — consistent with AR6 TCRE.
- The v1.4.1 parameter file in the FaIR repository has the same 841 member index and
  numerically identical values to the Zenodo original for all overlapping quantities; it
  is the same calibration re-expressed in `fair` 2.2 column names (86 vs 46 columns).
- Solar and Volcanic forcing rows in FaIR's `volcanic_solar.csv` are identical across all
  its scenarios, so a single series can be extracted.

## 4. User-facing API

```python
import goblin_fair as gf

res = gf.temperature_contribution(
    emissions,                    # pandas DataFrame, index = year (int)
    units="kt",                   # "t" | "kt" | "Mt" | "Gt", or dict per column
    background="ssp245",          # see gf.list_backgrounds()
    end_year=2100,                # last year simulated (<= 2500)
    members=None,                 # None = all 841; int = first N; list = explicit ids
)

res.summary()                 # DataFrame: index year, columns p5, p50, p95 (K)
res.summary(quantiles=(0.05, 0.17, 0.5, 0.83, 0.95))
res.ensemble                  # DataFrame: index year, columns = member id (K)
res.background_warming()      # same shape as summary(), absolute warming vs 1850–1900
res.plot()                    # matplotlib Axes: median line + 5–95 % band
res.metadata                  # dict: fair version, calibration, background, units, members, run date

gf.list_backgrounds()         # ["ssp119", "ssp126", "ssp245", "ssp370", "ssp434", "ssp460", "ssp534-over", "ssp585"]
```

Only these names are public in v0.1: `temperature_contribution`, `ContributionResult`,
`list_backgrounds`, `__version__`.

### Input rules (`emissions.py`)

- Index: integer years, strictly increasing, unique, within 1750–`end_year`. Gaps allowed
  (missing years count as zero extra emissions — no interpolation; documented and warned).
- Columns (case-insensitive): `CO2` **or** `CO2_FFI` and/or `CO2_AFOLU`; `CH4`; `N2O`.
  At least one required. `CO2` together with `CO2_FFI`/`CO2_AFOLU` is an error.
  `CO2` is treated as fossil (`CO2 FFI`); documented.
- Mass is **of the gas itself**: t CO2, t CH4, t N2O (not C, not N).
- Any column or unit containing `CO2e`/`CO2eq`/`GWP` → `ValueError` explaining that FaIR
  needs gas-specific emissions.
- Unknown columns, NaN, non-numeric values → `ValueError` naming the offending column/year.
- Negative values allowed (removals).
- Conversion to FaIR units: CO2 → Gt CO2/yr, CH4 → Mt CH4/yr, N2O → Mt N2O/yr.

### Output conventions

- Contribution = `T_surface(background + emissions) − T_surface(background)`, computed
  **per ensemble member** and then summarised. Units: K (≡ °C change).
- Year labels: FaIR `timebounds` (start of year). Reported year *Y* = temperature at
  1 January *Y*. Documented in the result and walkthrough.
- `background_warming()` is relative to the 1850–1900 mean of each member.

## 5. Internals

| Module | Responsibility | Depends on |
|---|---|---|
| `emissions.py` | Validate user DataFrame, normalise column names, convert units → FaIR species/units | pandas |
| `data/__init__.py` (or `_data.py`) | Locate bundled files via `importlib.resources`; load parameters (with member subsetting), species configs, forcing, background | pandas |
| `engine.py` | **Only module importing `fair`.** Build one `FAIR` instance with two scenarios (`background`, `background+emissions`), fill, run, return raw surface temperature array | fair, data |
| `results.py` | `ContributionResult`: difference, quantiles, ensemble frame, plot, metadata | pandas, numpy, matplotlib |
| `api.py` | `temperature_contribution`, `list_backgrounds`: glue | all above |

Engine recipe (mirrors FaIR's official calibrated-ensemble example):
`FAIR(ch4_method="Thornhill2021")` → `define_time(1750, end_year, 1)` →
`define_scenarios([bg, bg+"+emissions"])` → `define_configs(members)` →
`define_species(read_properties(species_csv))` → `allocate()` →
fill background emissions for both scenarios from bundled RCMIP subset (unit conversion as
in `fair.io.fill_from_rcmip`) → add converted user emissions to the second scenario →
fill Solar/Volcanic forcing × member `forcing_scale` → `fill_species_configs` →
`override_defaults(parameters_csv)` → initialise state → `run(progress=False)`.

Implementation must check, and record in the plan, whether loading the RCMIP subset
reuses `fair`'s own conversion code (preferred) or replicates `fill_from_rcmip`'s mapping.
If replicated, a slow test compares against `fill_from_rcmip` output.

Error handling: invalid inputs fail fast in `emissions.py` before any FaIR work;
unknown `background` / out-of-range `end_year` / invalid `members` raise `ValueError`
listing valid options. FaIR warnings are not silenced globally.

## 6. Bundled data and provenance

All model inputs ship in `src/goblin_fair/data/`. No network access at runtime.
`src/goblin_fair/data/DATA_SOURCES.md` records, **for each file**: upstream source
(DOI/URL and version or commit), retrieval date, upstream checksum, bundled-file SHA-256,
licence, citation, and every transformation applied.

| Bundled file | Upstream | Licence | Transformation |
|---|---|---|---|
| `calibrated_constrained_parameters_1.4.1.csv` | FaIR repo `examples/data/calibrated_constrained_ensemble/calibrated_constrained_parameters_calibration1.4.1.csv` (pinned commit); values from FaIR calibration data v1.4.1, Zenodo doi:10.5281/zenodo.10566813 | Apache-2.0 (FaIR repo) / CC-BY-4.0 (Zenodo) | none (renamed) |
| `species_configs_properties_1.4.1.csv` | FaIR repo, same folder, `species_configs_properties_calibration1.4.1.csv` | Apache-2.0 / CC-BY-4.0 | none (renamed) |
| `solar_volcanic_forcing.csv` | FaIR repo, same folder, `volcanic_solar.csv` | Apache-2.0 | one row each of Solar and Volcanic (rows identical across scenarios — verified by build script) |
| `background_emissions_rcmip_v5.1.0.csv` | RCMIP protocol v5.1.0 `rcmip-emissions-annual-means-v5-1-0.csv` (md5 `4044106f55ca65b094670e7577eaf9b3`), doi:10.5281/zenodo.4589756 | **CC-BY-SA-4.0** | filtered to Region = World, the 8 Tier-1/2 SSP scenarios (the two `ssp370-lowNTCF-*` AerChemMIP variants are deliberately excluded), the variables `fair` maps to v1.4.1 emission species, years 1750–2500 |

`scripts/build_data.py` downloads each upstream file, verifies its checksum, applies the
transformation, writes the bundled file and prints the SHA-256 values for
`DATA_SOURCES.md`. A test asserts bundled files match the recorded SHA-256.

Licensing note in README and `DATA_SOURCES.md`: package code is GPL-3.0; bundled data
keeps its upstream licence; the RCMIP subset remains CC-BY-SA-4.0.

Citations (README + `DATA_SOURCES.md`):
- Leach, N. J. et al. (2021) FaIRv2.0.0, *Geosci. Model Dev.* 14, 3007–3036, doi:10.5194/gmd-14-3007-2021.
- Smith, C. et al. (2024) fair-calibrate v1.4.1, *Geosci. Model Dev.* 17, 8569–8592, doi:10.5194/gmd-17-8569-2024.
- Smith, C. (2024) FaIR calibration data v1.4.1, Zenodo, doi:10.5281/zenodo.10566813.
- Nicholls, Z. et al. (2020) RCMIP Phase 1, *Geosci. Model Dev.* 13, 5175–5190, doi:10.5194/gmd-13-5175-2020.
- RCMIP protocol v5.1.0, Zenodo, doi:10.5281/zenodo.4589756.

Documented caveat: calibration v1.4.1 was constrained with emissions harmonised to 2022,
whereas RCMIP v5.1.0 SSPs follow CMIP6 history (to 2014) and SSP projections after. The
background climate therefore differs slightly from the calibration's own projections
(e.g. 2022 median warming 1.25 °C). This is a second-order effect for *marginal*
contributions and is stated in the README and walkthrough 02.

Each citation and licence must be confirmed against the upstream landing page during
implementation; `DATA_SOURCES.md` must not contain unverified claims.

## 7. Repository layout and tooling

```
goblin_fair/
├── pyproject.toml          Poetry; python ^3.10; GPL-3.0; src layout
├── poetry.lock
├── Makefile                install, test, test-all, lint, format, data, clean
├── README.md               badges, what/why, install, quickstart, data & citations, caveats, roadmap
├── CHANGELOG.md
├── LICENSE                 GPL-3.0
├── .gitignore              includes walkthrough/ and CLAUDE.md
├── CLAUDE.md               (git-ignored) project overview & conventions for Claude
├── docs/specs/             this spec
├── scripts/build_data.py
├── src/goblin_fair/
│   ├── __init__.py
│   ├── api.py
│   ├── emissions.py
│   ├── engine.py
│   ├── results.py
│   ├── _data.py
│   └── data/               4 CSVs + DATA_SOURCES.md
├── tests/
│   ├── conftest.py         fixtures; `slow` marker registration
│   ├── test_emissions.py   validation + unit conversion (fast)
│   ├── test_results.py     quantiles/ensemble/plot from synthetic arrays (fast)
│   ├── test_data.py        bundled files load; SHA-256 match DATA_SOURCES.md (fast)
│   └── test_engine.py      @slow: small-member real FaIR runs
└── walkthrough/            (git-ignored)
    ├── 01_quickstart.ipynb
    └── 02_how_it_works.ipynb
```

Dependencies: `fair = "2.2.4"`, `pandas`, `numpy`, `matplotlib`.
Optional Poetry groups: `test` (pytest, pytest-cov), `dev` (jupyterlab, ipykernel, ruff).

Makefile: `make test` runs `pytest -m "not slow"`; `make test-all` runs everything.

### Tests (behaviour they must pin)

Fast:
- Unit conversion: 1000 kt CO2 → 1.0 Gt CO2; 1000 kt CH4 → 1.0 Mt CH4; same for N2O.
- Per-column units dict works; `CO2` + `CO2_FFI` rejected; CO2e/GWP rejected with message;
  NaN / unknown column / non-integer or duplicate years rejected; negatives accepted.
- Results: summary quantiles computed per member from a synthetic difference array;
  column names; ensemble shape; `plot()` returns an Axes.
- Data: every bundled file exists and matches SHA-256 in `DATA_SOURCES.md`;
  `list_backgrounds()` returns the 8 SSPs.

Slow (few members, e.g. 5, short horizon where possible):
- Zero emissions → contribution exactly 0 for all members and years.
- Positive CO2 pulse → contribution ≥ 0 after the pulse and ~0 before it.
- Doubling CO2 emissions roughly doubles contribution (within tolerance — near-linear
  for small perturbations).
- CH4 step response decays after emissions stop (short-lived) while CO2 persists.
- Background loader reproduces `fill_from_rcmip` emissions for `ssp245` (if loader replicates it).

### Walkthroughs (git-ignored, run against the installed package)

- `01_quickstart.ipynb` — build a toy emissions DataFrame (e.g. constant 10 Mt CO2, 0.5 Mt
  CH4, 0.02 Mt N2O per year 2025–2050), one call, `summary()`, `plot()`, how to read median
  and 5–95 % range, what "marginal against SSP2-4.5" means in one paragraph.
- `02_how_it_works.ipynb` — marginal method with a picture (background vs perturbed),
  ensemble spread, CO2 vs CH4 response shapes, where each data file comes from (links to
  `DATA_SOURCES.md`), known caveats.

### README

Badges (static shields.io, as in sibling FORESIGHT packages): Python 3.10+, licence
GPL-3.0, packaging Poetry, FaIR 2.2.4, calibration v1.4.1, tests, code style ruff,
version 0.1.0. Sections: overview, install, quickstart, how it works (short), data
sources & citations, caveats, roadmap (objectives 2 & 3), FORESIGHT context, licence.

### CLAUDE.md (git-ignored)

Project purpose and the three objectives; the design decisions table; module
responsibilities and the rule that only `engine.py` imports `fair`; data provenance rule
(no bundled data without a `DATA_SOURCES.md` entry); commands (`make test`, etc.);
walkthrough folder is git-ignored; pointer to this spec.

## 8. Out of scope for v0.1

- Per-gas attribution runs (`by_gas=True`) — natural v0.2 addition.
- National inventory loaders (EPA Ireland, EEA, PRIMAP-hist, UNFCCC) — objectives 2 & 3.
- F-gases, aerosols and precursors in user emissions.
- Other calibrations, custom background scenarios, concentration- or forcing-driven runs.
- Other outputs (ERF, concentrations, ocean heat).
- CI workflows, Sphinx docs, PyPI publishing.

## 9. Success criteria

1. `poetry install --with test,dev` works in a clean checkout; `make test` and
   `make test-all` pass.
2. `temperature_contribution` on the quickstart emissions with all 841 members completes
   in under ~60 s and gives a positive, sensible contribution.
3. Every bundled file is traceable via `DATA_SOURCES.md` and reproducible via
   `scripts/build_data.py`.
4. Both walkthrough notebooks run top-to-bottom without error.
5. `walkthrough/` and `CLAUDE.md` are not tracked by git.
