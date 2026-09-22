# Plan: audit the EU and Irish data, build one SQLite database, plot the pathways with FaIR

Date: 2026-09-19. Status: **done, in narrowed form.** Colm then decided:
- **only the 3 NZero scenarios**;
- **only the gas totals**;
- **the Irish workbook is left for validation later**.

What was built:
- `scripts/build_eu_db.py` (`make eu-db`), which writes `EU-data/eu27_net_zero.sqlite`;
- tests in `tests/test_build_eu_db.py`;
- `walkthrough/07_eu27_net_zero.ipynb`.

The full documentation, including scenario definitions, what each FaIR input contains and why
the CH4/N2O breakdowns don't add up, is in `EU-data/README.md`. That folder is git-ignored
because of the data licence. The audit below is kept as the record; where it differs, the
README wins.

**Correction:** `300`, `500` and `800` are carbon prices in €/t CO2 in 2040, not CO2 budgets
(Byers et al. 2023, §2.2.1). Two of the three NZero scenarios (`NZero` and `NZero_bioLim12`)
are identical in the data.

## Goal

1. Extract Ireland's emissions pathways from the Irish workbook.
2. Extract **every EU27 net-zero pathway** from the ESABCC workbook.
3. Put both into one SQLite database.
4. Find out what all the categories are, and show they can be reduced to the handful FaIR needs.
5. Plot the emissions pathways and the warming they cause, using `goblin_fair`.

## What is in the data (checked 2026-09-19)

### `EU-data/ire_ch4-co2_temps_0.1.3.xlsx` (Irish, 120 kB)

| Sheet | What it holds |
|---|---|
| `ire_emissions` | **The data we want.** 5 scenarios × 4 gases, annual 2020–2100, in kt |
| `ire_temp_CH4_N2O_CO2`, `CH4`, `N2O`, `CO2_FOSSIL`, `CO2 AFOLU`, `CH4+CO2+N2O` | MAGICC v7.5.3 temperature results for those scenarios (on ssp126). Useful as a **cross-check** for FaIR |
| `CH4_by_country` | CH4 in 2020 for 232 countries (Tg). Source not stated |

- The 5 scenarios are: BAU (LUR); Net zero AFOLU (livestock protein, LUR); Split gas AFOLU 1; Split gas AFOLU 2; TN compliant 1.5C world.
- The 4 variables are `CO2|MAGICC Fossil and Industrial`, `CO2|MAGICC AFOLU`, `CH4` and `N2O`. They map one-to-one onto goblin_fair's `CO2_FFI`, `CO2_AFOLU`, `CH4` and `N2O`.
- Quirk: the `region` column says "World", but the numbers are Ireland's (650 kt CH4 in 2020).

### `EU-data/1687184510132-ESABCC_v2.0_ESABCC_REMIND_3.2.xlsx` (EU, 72 MB)

The European Scientific Advisory Board on Climate Change scenario database, v2.0
(doi:10.5281/zenodo.8035686). It is in the standard IAMC layout: Model, Scenario, Region,
Variable, Unit, then one column per year from 1995 to 2100.

- 365,100 rows, 1 model (REMIND 3.2), **30 scenarios**, 41 regions and 1,020 variables.
- **All 30 scenarios are EU net-zero pathways.** EU27 greenhouse gases reach net zero between
  2039 and 2047. All are "C1b: Below 1.5 °C with low overshoot" and all passed vetting.
  16 pass the database's own feasibility flag and 14 fail it.
- The scenario names are a grid of three choices:
  - effort-sharing family: `NZero`, `def`, `flex` or `rigid`;
  - biomass limit: none, `bioLim12` or `bioLim7p5`;
  - carbon price in 2040: `300`, `500` or `800` €/t CO2. `NZero` follows its own reference price path.
- **Ireland is not in it on its own.** REMIND groups it with the UK ("United Kingdom and
  Ireland"). The EU27 totals include Ireland.
- Licence: reuse is allowed with citation, but *redistribution of substantial portions is
  restricted*. So the database stays local and git-ignored, like `EU-data/` itself.

### The categories, and how far they simplify

EU27 has 346 variables per scenario. By top-level group:

| Group | Variables | Needed for FaIR? |
|---|---|---|
| Final / Secondary / Primary Energy, Capacity, Capacity Additions, Trade, Price, Energy Service, Hydrogen, GDP, Population, Consumption, Import dependency, Diagnostics | 291 | No. This is energy-system detail |
| Carbon Capture / Removal / Sequestration | 22 | No. It is already netted into the CO2 totals |
| **Emissions** (incl. Gross Emissions) | 33 | **4 of them** |

There are also 671 "AR6 climate diagnostics" variables. They exist for the World region only,
and hold MAGICC temperatures, forcing and harmonised emissions. They are not needed, but the
World temperatures could serve as a second cross-check.

**So yes, it simplifies to four columns** per scenario:

| goblin_fair column | ESABCC EU27 variable | Unit |
|---|---|---|
| `CO2_FFI` | `Emissions|CO2|Energy and Industrial Processes` | Mt CO2/yr |
| `CO2_AFOLU` | `Emissions|CO2|AFOLU` | Mt CO2/yr |
| `CH4` | `Emissions|CH4` | Mt CH4/yr |
| `N2O` | `Emissions|N2O` | kt N2O/yr |

There is also an optional methane split, using stream labels:
- `CH4:biogenic` = Agriculture + Land + Waste;
- `CH4:fossil` = the total minus biogenic. See issue 3 for why it is the total minus.

## Problems found, with a recommendation for each

1. **The EU data is only every 5 years** (every 10 after 2060), with values in 2005, 2010,
   2015, ... goblin_fair counts missing years as *zero*. **Recommendation:** interpolate
   linearly to single years before anything else.
2. **Short history.** EU data starts in 2005 and Irish data in 2020. Results will mean
   "warming from emissions since 2005 (or 2020)", not historical responsibility. For
   `neutral_pathway` the start year matters a lot: in today's tests the cut needed was
   0.63 %/yr with history from 1950, 0.74 from 1970 and 1.05 from 1990. **Recommendation:**
   accept "since 2005 / since 2020" for the first plots, and label them that way. Adding
   pre-2005 history (e.g. PRIMAP-hist) is a separate step.
3. **The sub-categories don't add up.** Agriculture + Land + Energy + Waste falls short of
   the total by 13–17 % for CH4 and 25–31 % for N2O in 2005–2020. The gap shrinks to 0–4 % by
   2050. **Recommendation:** always use the totals. If a methane split is needed, the fossil
   stream is the total minus the biogenic parts, so nothing is lost.
4. **F-gases are only given in CO2-equivalent**, so FaIR cannot use them. They are left out,
   and the plots say so.
5. **Which background world?** Every EU scenario is a 1.5 °C world. **Recommendation:** use
   `ssp119` as the main background and `ssp245` as a sensitivity. **Choice for Colm.**
6. **Irish provenance.** File version 0.1.3, model label "CPD", no source note.
   **Choice for Colm:** say where these numbers come from, so it can be recorded.

## Steps

### 1. `scripts/build_eu_db.py` builds `EU-data/pathways.sqlite`
- Read both workbooks once (about 40 s for the large one).
- Write four tables:

| Table | Rows | Contents |
|---|---|---|
| `scenarios` | 35 | source, scenario, and parsed family / biomass limit / carbon price; feasibility flag and net-zero years from `meta`; the Irish names |
| `variables` | 1,020 | every ESABCC variable with its unit, top-level group, regions it appears in, and a flag for "used for FaIR". **This is the category catalogue** |
| `raw` | one row per reported value | long format (source, scenario, region, variable, unit, year, value). All EU27 variables for all 30 scenarios, plus the 20 Irish rows. Empty cells dropped |
| `fair_input` | 35 × years | one row per scenario and year, **interpolated to single years**, in kt: `CO2_FFI`, `CO2_AFOLU`, `CH4`, `N2O`, `CH4_biogenic`, `CH4_fossil` |

- Run it with `make eu-db`.
- The SQLite file lives in `EU-data/`, which is already git-ignored.

### 2. Tests (TDD, fast, with a tiny made-up workbook, not the real files)
- The interpolation fills every year and keeps the reported years exactly.
- Unit conversion (Mt to kt) is correct.
- `CH4_biogenic + CH4_fossil == CH4`.
- The scenario-name parser handles all 30 names.
- Rows missing a gas are reported, not silently zeroed.

### 3. Notebook `walkthrough/07_eu_and_irish_pathways.ipynb`
- **The categories:** a table from `variables`, showing the 1,020 variables shrinking to 4.
- **The emissions:** one panel per gas. The 30 EU27 pathways are drawn as thin lines coloured
  by family, with the median in bold. The 5 Irish scenarios are drawn the same way.
- **The warming:** `gf.temperature_contribution(df, units="kt", background="ssp119")` for
  each scenario:
  - 35 runs at about 14 s each is about 8 minutes with all 841 members;
  - `members=100` is used while exploring.
  - Plot the median warming per scenario, with the 5–95 % range for one representative
    scenario.
- **Cross-check:** run Ireland's 5 scenarios on `ssp126` and compare the results with the
  MAGICC numbers in the Irish workbook. We expect the same shape and a similar size, not
  identical numbers. Write down any big difference.
- One sentence under each chart saying what it shows.

### 4. Later (not in this plan)
- Pre-2005 history.
- A `goblin_fair.inventories` reader.
- `neutral_pathway` for the EU and Ireland.

## Verification
- `make test` passes, and the new tests fail before the code exists.
- Row counts in the database match the workbook: 30 EU scenarios × 346 EU27 variables; 5 Irish
  scenarios × 4 gases.
- For each scenario, `fair_input` in a reported year equals the workbook value exactly, after
  unit conversion.
- The notebook runs end to end with `make walkthrough`.
