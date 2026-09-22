# Data sources

Every file goblin_fair reads at runtime is in this folder. This document says
where each one came from, under what licence, how to cite it, and exactly what
was changed. Nothing is downloaded at runtime.

All facts below were checked on 2026-09-15 against the upstream landing pages
(Zenodo records, Crossref DOI metadata, the FaIR GitHub repository) and the
downloaded files themselves.

## Summary

| Bundled file | What it is | Upstream | Licence | Changed? |
|---|---|---|---|---|
| `calibrated_constrained_parameters_1.4.1.csv` | 841 calibrated, constrained FaIR parameter sets (one row per ensemble member) | FaIR calibration v1.4.1 (Smith 2024), as distributed in the FaIR repository | Apache-2.0 (FaIR repo); CC-BY-4.0 (Zenodo record) | No (renamed) |
| `species_configs_properties_1.4.1.csv` | Properties and default configs of the 61 FaIR species for calibration v1.4.1 | As above | Apache-2.0 (FaIR repo); CC-BY-4.0 (Zenodo record) | No (renamed) |
| `solar_volcanic_forcing.csv` | Solar and volcanic effective radiative forcing, 1750-2500 | FaIR repository example data for calibration v1.4.1 | Apache-2.0 | Yes: collapsed to one series each, interpolated to annual |
| `background_emissions_rcmip_v5.1.0.csv` | Global emissions of all 51 FaIR emission species for 8 SSP scenarios, 1750-2500 | RCMIP protocol v5.1.0 | CC-BY-SA-4.0 | Yes: subset, renamed variables, interpolated |

---

## 1. `calibrated_constrained_parameters_1.4.1.csv`

- **Upstream file:** `examples/data/calibrated_constrained_ensemble/calibrated_constrained_parameters_calibration1.4.1.csv`
  in the FaIR repository, https://github.com/OMS-NetZero/FAIR, at commit
  `28572bb00e40d73f83f3365395fe8bc3a1b60bb9` (2024-07-23, the last commit to change that folder).
  Raw URL: `https://raw.githubusercontent.com/OMS-NetZero/FAIR/28572bb00e40d73f83f3365395fe8bc3a1b60bb9/examples/data/calibrated_constrained_ensemble/calibrated_constrained_parameters_calibration1.4.1.csv`
- **Upstream SHA-256:** `7b6c5d9fa0b0b0d3eb47189bf5d63cbf77e752ddac682947abee5ff529206780`
- **Origin of the values:** *FaIR calibration data*, version 1.4.1, Chris Smith, Zenodo,
  published 2024-01-25, doi:[10.5281/zenodo.10566813](https://doi.org/10.5281/zenodo.10566813)
  (file `calibrated_constrained_parameters.csv`). The FaIR repository copy holds the same
  841 members (identical member ids) with numerically identical values for every quantity
  present in both files; it expresses them in the column names that `fair` 2.2's
  `FAIR.override_defaults` reads (86 columns, versus 46 in the Zenodo file). This was
  verified by loading both files and comparing values.
- **Method:** 1.6 million prior parameter sets, constrained to 841 posterior members against
  observed warming and IPCC AR6 assessed ranges (ECS, TCR, aerosol forcing, ocean heat
  uptake, CO2 concentration). See Smith et al. (2024).
- **Licence:** the FaIR repository is licensed Apache-2.0; the Zenodo record is CC-BY-4.0.
- **Transformation:** none. Copied byte-for-byte and renamed.

## 2. `species_configs_properties_1.4.1.csv`

- **Upstream file:** `examples/data/calibrated_constrained_ensemble/species_configs_properties_calibration1.4.1.csv`,
  same repository and commit as above.
- **Upstream SHA-256:** `42d04aa1a8f385cc53eae22beab26f857c535c5aa7dfdb98176d712bfc0c95a0`
- **Contents:** 61 species (51 driven by emissions, 8 calculated, 2 driven by forcing:
  Solar and Volcanic) with their gas-cycle, forcing and chemistry properties for
  calibration v1.4.1.
- **Licence:** Apache-2.0 (FaIR repository); part of calibration v1.4.1 (CC-BY-4.0 on Zenodo).
- **Transformation:** none. Copied byte-for-byte and renamed.

## 3. `solar_volcanic_forcing.csv`

- **Upstream file:** `examples/data/calibrated_constrained_ensemble/volcanic_solar.csv`,
  same repository and commit as above.
- **Upstream SHA-256:** `621b551dafa6ff0e5a789b94a81a12876d796832c0e15f627545af40d6de58e5`
- **Contents upstream:** Solar and Volcanic effective radiative forcing (W m-2) for 7 example
  scenarios, 1750-2300 annually plus 2301 and 2501.
- **Licence:** Apache-2.0 (FaIR repository).
- **Transformation** (`scripts/build_data.py`, `build_forcing`):
  1. The build checks that the Solar rows are identical across all 7 scenarios, and the
     same for Volcanic. They are, because natural forcing does not depend on the
     emissions scenario. One row of each is kept.
  2. Linearly interpolated onto integer years 1750-2500 (FaIR "timebounds"), which is
     what `fair`'s own CSV reader does.
  3. Written as columns `year, Solar, Volcanic`.
- **At runtime:** each member's forcing is multiplied by its calibrated
  `forcing_scale[Solar]` / `forcing_scale[Volcanic]`, as in FaIR's calibrated-ensemble
  example (`fair` does not apply `forcing_scale` to species supplied as forcing).

## 4. `background_emissions_rcmip_v5.1.0.csv`

- **Upstream file:** `rcmip-emissions-annual-means-v5-1-0.csv` from the Reduced Complexity
  Model Intercomparison Project (RCMIP) protocol, version v5.1.0, by Zebedee Nicholls and
  Jared Lewis, Zenodo, published 2021-03-09,
  doi:[10.5281/zenodo.4589756](https://doi.org/10.5281/zenodo.4589756).
  Downloaded from `https://rcmip-protocols-au.s3-ap-southeast-2.amazonaws.com/v5.1.0/rcmip-emissions-annual-means-v5-1-0.csv`,
  the URL `fair` 2.2.4 itself uses in `fair.io.fill_from_rcmip`.
- **Upstream MD5:** `4044106f55ca65b094670e7577eaf9b3`, the hash pinned in `fair` 2.2.4.
- **Contents upstream:** CMIP6 historical emissions and SSP scenario projections, many
  regions and sectors, 1750-2500 (annual history, sparser future years).
- **Licence:** **CC-BY-SA-4.0** (ShareAlike). This derived subset is therefore also
  distributed under CC-BY-SA-4.0.
- **Transformation** (`scripts/build_data.py`, `build_background`):
  1. Kept `Region == "World"` and the eight SSP scenarios `ssp119, ssp126, ssp245, ssp370,
     ssp434, ssp460, ssp534-over, ssp585`. The two `ssp370-lowNTCF-*` AerChemMIP variants
     are excluded on purpose.
  2. For each of the 51 emission-driven species in file 2, selected the one RCMIP variable
     ending in the name `fair` maps it to. `CO2 FFI` maps to `CO2|MAGICC Fossil and Industrial`,
     `CO2 AFOLU` maps to `CO2|MAGICC AFOLU`, and every other species maps to its name without
     hyphens. This is the mapping in `fill_from_rcmip`. The build fails unless each
     scenario and species matches exactly one row.
  3. Filled RCMIP's gaps between years by linear interpolation. Then interpolated linearly,
     extrapolating where needed, from the RCMIP mid-year points onto timepoints
     1750.5-2500.5. This repeats what `fill_from_rcmip` does step for step.
  4. Renamed each variable to its FaIR species name and kept RCMIP's unit string
     (e.g. `Mt CO2/yr`, `kt N2O/yr`). Unit conversion happens at runtime inside `fair`
     (`FAIR.fill_from_pandas`).
  5. Written in `fair`'s CSV format: `scenario, region, variable, unit, 1750.5, ..., 2500.5`
     (408 rows = 8 scenarios × 51 species).
- **Check:** the `network`-marked test `test_bundled_background_matches_fill_from_rcmip`
  confirms that `fair` gets the same emissions from this file as from `fill_from_rcmip`.

---

## Licensing

- goblin_fair's **code** is GPL-3.0.
- The **bundled data** keep their upstream licences (above). Apache-2.0 and CC-BY-4.0
  require attribution. CC-BY-SA-4.0 requires attribution, and adaptations must be shared
  under the same licence. All of these are compatible with redistribution alongside
  GPL-3.0 code.

## How to cite

If you use goblin_fair results, cite the underlying model and data:

- Leach, N. J., Jenkins, S., Nicholls, Z., Smith, C. J., Lynch, J., Cain, M., Walsh, T.,
  Wu, B., Tsutsui, J., and Allen, M. R. (2021). FaIRv2.0.0: a generalized impulse response
  model for climate uncertainty and future scenario exploration. *Geoscientific Model
  Development*, 14, 3007-3036. doi:[10.5194/gmd-14-3007-2021](https://doi.org/10.5194/gmd-14-3007-2021)
- Smith, C., Cummins, D. P., Fredriksen, H.-B., Nicholls, Z., Meinshausen, M., Allen, M.,
  Jenkins, S., Leach, N., Mathison, C., and Partanen, A.-I. (2024). fair-calibrate v1.4.1:
  calibration, constraining, and validation of the FaIR simple climate model for reliable
  future climate projections. *Geoscientific Model Development*, 17, 8569-8592.
  doi:[10.5194/gmd-17-8569-2024](https://doi.org/10.5194/gmd-17-8569-2024)
- Smith, C. (2024). FaIR calibration data (1.4.1). Zenodo.
  doi:[10.5281/zenodo.10566813](https://doi.org/10.5281/zenodo.10566813)
- Nicholls, Z. R. J., Meinshausen, M., Lewis, J., et al. (2020). Reduced Complexity Model
  Intercomparison Project Phase 1: introduction and evaluation of global-mean temperature
  response. *Geoscientific Model Development*, 13, 5175-5190.
  doi:[10.5194/gmd-13-5175-2020](https://doi.org/10.5194/gmd-13-5175-2020)
- Nicholls, Z., and Lewis, J. (2021). Reduced Complexity Model Intercomparison Project
  (RCMIP) protocol (v5.1.0). Zenodo. doi:[10.5281/zenodo.4589756](https://doi.org/10.5281/zenodo.4589756)

## Known caveats

- **Background history differs slightly from the calibration's.** Calibration v1.4.1 was
  constrained using emissions harmonised to 2022. The RCMIP v5.1.0 SSPs instead follow
  CMIP6 historical emissions (to 2014) and the SSP projections after that. The background
  climate therefore does not exactly match the calibration's own projections: with the full
  ensemble on `ssp245`, median warming above 1850-1900 is 1.25 °C in 2022 and 2.63 °C in
  2100. For a *marginal* contribution (the difference between two runs on the same
  background) this is a second-order effect.
- **The draft CMIP7 "extension" scenarios in FaIR's example folder are not used.**
  FaIR's authors advise against using them naively.

## How to rebuild

```bash
make data        # = poetry run python scripts/build_data.py
```

The script downloads each upstream file into the pooch cache, checks it against the hash
above, rebuilds the four bundled files and prints their SHA-256 values. The build is
deterministic: running it twice gives the same checksums. If the checksums change, update
the table below, or `tests/test_data.py` will fail.

## Checksums of bundled files

| file | sha256 |
|---|---|
| `calibrated_constrained_parameters_1.4.1.csv` | `7b6c5d9fa0b0b0d3eb47189bf5d63cbf77e752ddac682947abee5ff529206780` |
| `species_configs_properties_1.4.1.csv` | `42d04aa1a8f385cc53eae22beab26f857c535c5aa7dfdb98176d712bfc0c95a0` |
| `solar_volcanic_forcing.csv` | `bb45e15cabdaf7dec54b3fdfa6614d516b3905a736faa015b888f6558bf916c7` |
| `background_emissions_rcmip_v5.1.0.csv` | `b788d06db046a0adb149a4b7f998b6441ec6f757b69a6ab04749af816bdb7639` |
