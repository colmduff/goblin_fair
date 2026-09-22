# goblin_fair

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](https://github.com/colmduff/goblin_fair/blob/main/LICENSE)
[![Packaging: Poetry](https://img.shields.io/badge/packaging-poetry-1e293b.svg)](https://python-poetry.org/)
[![FaIR 2.2.4](https://img.shields.io/badge/FaIR-2.2.4-2c7fb8.svg)](https://pypi.org/project/fair/2.2.4/)
[![Calibration v1.4.1](https://img.shields.io/badge/calibration-v1.4.1-41ab5d.svg)](https://doi.org/10.5281/zenodo.10566813)
[![Background: RCMIP v5.1.0](https://img.shields.io/badge/background-RCMIP%20v5.1.0-6a51a3.svg)](https://doi.org/10.5281/zenodo.4589756)
[![Tests: pytest](https://img.shields.io/badge/tests-pytest-brightgreen.svg)](https://github.com/colmduff/goblin_fair/tree/main/tests)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://github.com/astral-sh/ruff)
[![Version](https://img.shields.io/badge/version-0.1.0-orange.svg)](https://github.com/colmduff/goblin_fair/blob/main/CHANGELOG.md)

**How much global warming does a set of emissions cause?** goblin_fair answers
that question with one function call. It uses the
[FaIR](https://github.com/OMS-NetZero/FAIR) simple climate model, the calibrated
and constrained parameter ensemble published with it, and fully documented
input data.

FaIR can already do this, but it takes around 25 lines of setup before the first
run. goblin_fair hides that setup and keeps the science visible: every number it
uses is traced to its source in
[`DATA_SOURCES.md`](src/goblin_fair/data/DATA_SOURCES.md).

goblin_fair is part of the FORESIGHT family of tools, alongside `goblin_lite`
and `agrisyn`.

## Install

```bash
git clone https://github.com/colmduff/goblin_fair.git
cd goblin_fair
poetry install                  # the package
poetry install --with test,dev  # plus pytest, ruff and Jupyter
```

All model data ships inside the package (about 4 MB), so no downloads are needed
at runtime.

## Quickstart

```python
import pandas as pd
import goblin_fair as gf

# Emissions per year, as the mass of each gas (not CO2-equivalent)
emissions = pd.DataFrame(
    {"CO2": 10.0, "CH4": 0.5, "N2O": 0.02},      # Mt per year
    index=range(2025, 2051),
)

res = gf.temperature_contribution(emissions, units="Mt")   # ~20 s, 841 members

res.summary()        # year x [p5, p50, p95], kelvin
res.plot()           # median with the 5-95 % range shaded
res.ensemble         # year x member, for your own analysis
res.metadata         # FaIR version, calibration, background, units, ...
```

```
      p5 (mK)  p50 (mK)  p95 (mK)
year
2030     0.11      0.14      0.19
2050     0.52      0.70      0.93
2075     0.27      0.40      0.60
2100     0.17      0.26      0.42
```

Warming peaks when the emissions stop in 2050. It then falls as the methane
breaks down, while the CO2 part persists.

Useful options:

| Argument | Default | Meaning |
|---|---|---|
| `units` | `"kt"` | `"t"`, `"kt"`, `"Mt"`, `"Gt"`, or a dict per column |
| `background` | `"ssp245"` | global scenario the emissions belong to; see `gf.list_backgrounds()` |
| `end_year` | `2100` | last year simulated (1902-2500) |
| `members` | all 841 | an int N runs only the first N members, which is quicker for exploring |
| `method` | `"leave_one_out"` | `"add"` for extra emissions that are not already in the background |

`gf.neutral_pathway()` answers the reverse question; see below.

## How it works

1. **Leave-one-out contribution.** FaIR runs a global background scenario
   (SSP2-4.5 by default) twice in one go: once as it is (the world *with* your
   emissions, which are part of its world totals) and once with your emissions
   taken out (the world *without* them). Your contribution is the difference:
   the warming that would not have happened without you. Both runs keep the
   non-linear parts of the climate system, such as CO2 uptake saturating and
   methane lifetime changing. For extra emissions that are not already in the
   background, `method="add"` compares the SSP plus your emissions with the SSP.
   Because of the non-linearity, leave-one-out contributions of several emitters
   do not add up exactly to their combined contribution.
2. **Calibrated ensemble.** Each of the 841 parameter sets is a plausible version
   of the climate system, constrained to match observed warming and the IPCC AR6
   assessed ranges. The difference is taken member by member, and `summary()`
   reports the spread of those differences.
3. **Gas-specific inputs.** CO2, CH4 and N2O behave very differently. Methane
   warms strongly but mostly disappears within a few decades, while CO2 warming
   persists for centuries. For that reason goblin_fair accepts the mass of each
   gas and rejects CO2-equivalent totals.
4. **Years.** Emissions in year *Y* are spread across that year. Temperature for
   year *Y* is the value at the start of that year.

The walkthrough notebooks go through each step with plots.

## Working backwards: what would neutrality take?

The same model can answer the reverse question: what would this entity have to emit to
stop adding warming?

```python
answer = gf.neutral_pathway(
    emissions,          # the entity's emissions, history included
    solve="CH4",        # the column to solve for
    from_year=2025,     # hold warming at its 2025 level, and start cutting then
    by_year=2050,       # be back at that level by 2050 and stay there
)

answer.decline["p50"]        # e.g. 1.4 -> cut 1.4 % a year
answer.cut_by(2050)          # e.g. 29 -> 29 % below 2025 by 2050
answer.pathway               # the emissions that implies, with its range
answer.allowance             # that pathway minus the one you gave
answer.verification          # what the final FaIR run actually did
```

The search runs FaIR at different cut rates and narrows in on the smallest one that
works, so every number comes from a real run. Each ensemble member gets its own required
rate, which is where the p5-p95 range comes from, and `verification["share_neutral"]`
says for what share of members the reported pathway really is neutral.

Two choices define the question, and both are yours:

- `from_year`: the warming level that must not be exceeded, and the first year of action.
- `by_year`: when that level must be met again. Warming already in the pipeline keeps
  rising for a few years whatever the entity does, so the years in between are a
  transition and are not judged.

Going the other way, a `ContributionResult` says when a pathway you already have becomes
neutral:

```python
res = gf.temperature_contribution(emissions)
res.warming_rate(window=10)                      # K per year, per member
res.neutrality(from_year=2025, rule="peak")      # the year it stops rising
```

### Splitting a gas into streams

If an inventory separates a gas, a column can carry a label: `CH4:biogenic`,
`CH4:fossil`. FaIR has one methane, so labels are added together before the run; a label
only lets one stream be reported, or solved for, on its own. Splitting is accounting, not
physics, and the streams' contributions do not add up exactly to the whole, because
methane's lifetime depends on how much methane is in the air.

## Data sources

| Data | Source | Licence |
|---|---|---|
| Calibrated parameter ensemble (841 members) and species properties | FaIR calibration v1.4.1, Smith (2024), [doi:10.5281/zenodo.10566813](https://doi.org/10.5281/zenodo.10566813), as distributed in the FaIR repository | Apache-2.0 / CC-BY-4.0 |
| Solar and volcanic forcing | FaIR repository example data for calibration v1.4.1 | Apache-2.0 |
| Background emissions (8 SSPs, all species) | RCMIP protocol v5.1.0, [doi:10.5281/zenodo.4589756](https://doi.org/10.5281/zenodo.4589756) | CC-BY-SA-4.0 |

[`DATA_SOURCES.md`](src/goblin_fair/data/DATA_SOURCES.md) records, for every
file: the upstream URL and pinned version or commit, the upstream checksum, the
licence, the citation, each transformation applied, and the SHA-256 of the
bundled file. `make data` rebuilds all four files from the upstream sources, and
the build is deterministic. The test suite checks the checksums.

### Please cite

- Leach, N. J. et al. (2021). FaIRv2.0.0: a generalized impulse response model for climate uncertainty and future scenario exploration. *Geosci. Model Dev.*, 14, 3007-3036. [doi:10.5194/gmd-14-3007-2021](https://doi.org/10.5194/gmd-14-3007-2021)
- Smith, C. et al. (2024). fair-calibrate v1.4.1: calibration, constraining, and validation of the FaIR simple climate model for reliable future climate projections. *Geosci. Model Dev.*, 17, 8569-8592. [doi:10.5194/gmd-17-8569-2024](https://doi.org/10.5194/gmd-17-8569-2024)
- Nicholls, Z. R. J. et al. (2020). Reduced Complexity Model Intercomparison Project Phase 1: introduction and evaluation of global-mean temperature response. *Geosci. Model Dev.*, 13, 5175-5190. [doi:10.5194/gmd-13-5175-2020](https://doi.org/10.5194/gmd-13-5175-2020)

## Caveats

- **Background history.** Calibration v1.4.1 was constrained using emissions
  harmonised to 2022, but the RCMIP SSPs follow CMIP6 history. As a result the
  background runs slightly warm: the median is 1.25 °C above 1850-1900 in 2022.
  This matters little for a marginal contribution.
- **A single `CO2` column is treated as fossil CO2.** Use `CO2_FFI` and
  `CO2_AFOLU` to split out land-use CO2.
- **Only CO2, CH4 and N2O** are accepted as inputs. F-gases, aerosols and
  ozone precursors are not.
- **Internal variability.** The calibration includes stochastic internal
  variability. It is identical in the "with" and "without" runs, so it
  cancels exactly in the contribution but shows up in `background_warming()`.

## Development

```bash
make install      # poetry install --with test,dev
make test         # fast tests (no FaIR runs, no downloads)
make test-all     # + real FaIR runs and the upstream-data cross-check
make lint         # ruff
make data         # rebuild bundled data from upstream (network)
make walkthrough  # execute the walkthrough notebooks
```

Only `src/goblin_fair/engine.py` imports `fair`. The walkthrough notebooks live
in `walkthrough/`, which is kept local and ignored by git.

## Roadmap

1. **v0.1:** a simple, documented workflow for the temperature impact of emissions.
2. **Next:** Irish emissions inventories, and the temperature contribution of Ireland.
3. **Then:** the EU as a bloc, individual European countries, or any other country.

Also planned: splitting results by gas, and more input gases.

## Licence

The code is licensed under [GPL-3.0](LICENSE). The bundled data keep their
upstream licences, listed above and in `DATA_SOURCES.md`.
