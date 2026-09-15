# goblin_fair v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Poetry-packaged Python library whose one call, `temperature_contribution(emissions)`, returns the marginal global temperature contribution of CO2/CH4/N2O emissions using the FaIR 2.2.4 calibrated ensemble (v1.4.1) on an RCMIP v5.1.0 SSP background, with every bundled data file documented.

**Architecture:** `emissions.py` validates and converts user input; `_data.py` loads bundled data; `engine.py` (the only module importing `fair`) runs one FaIR instance with two scenarios, `background` and `perturbed`; `results.py` turns the two temperature arrays into a `ContributionResult`; `api.py` wires them. `scripts/build_data.py` regenerates the bundled data from checksummed upstream sources.

**Tech Stack:** Python >=3.10, Poetry, fair 2.2.4, pandas, numpy, matplotlib, pytest, ruff, Jupyter.

**Spec:** `docs/specs/2026-09-15-goblin-fair-v0.1-design.md`

## Global Constraints

- `fair` pinned to exactly `2.2.4`; calibration v1.4.1; RCMIP v5.1.0.
- Only `src/goblin_fair/engine.py` may `import fair` (tests may import `fair` for cross-checks).
- Gases: `CO2` or `CO2_FFI`/`CO2_AFOLU`, `CH4`, `N2O`; mass of the gas itself; units `t|kt|Mt|Gt`.
- FaIR target units: CO2 → Gt CO2/yr, CH4 → Mt CH4/yr, N2O → Mt N2O/yr.
- Backgrounds: `ssp119, ssp126, ssp245, ssp370, ssp434, ssp460, ssp534-over, ssp585`.
- No network access at runtime. Every bundled file has a `DATA_SOURCES.md` entry with SHA-256.
- Package code GPL-3.0; bundled data keeps upstream licence (RCMIP subset CC-BY-SA-4.0).
- `walkthrough/` and `CLAUDE.md` are git-ignored.
- Author: Colm Duffy <colm.p.duffy@gmail.com>. Commits end with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

## Refinements to the spec discovered while planning (verified against fair 2.2.4 source)

1. **Emission years must be `< end_year`.** Emissions in year *Y* occupy FaIR timepoint *Y*+0.5 and first
   affect temperature at timebound *Y*+1, so a year equal to `end_year` has no effect. Valid: `1750 <= year <= end_year - 1`.
2. **`end_year` range is `1902..2500`** so the 1850–1900 baseline exists and RCMIP data covers the run.
3. **1850–1900 baseline** uses FaIR's own convention: mean over timebounds 1850–1901 with half weights at both ends.
4. **Stochastic variability** (`stochastic_run=True`, `use_seed=True` in v1.4.1) is kept as calibrated.
   `fair` indexes the noise by `[timepoint, None(scenario), config]`, so it is identical in both scenarios
   and cancels in the difference. A slow test pins this (zero emissions → zero contribution).
5. **Background loading reuses fair's own reader.** The bundled background CSV is written in `fair`'s
   CSV format (`scenario, region, variable, unit, <timepoints>`) using fair species names and RCMIP unit
   strings, pre-interpolated exactly as `fair.io.fill_from_rcmip` does. The engine calls `FAIR.fill_from_pandas`,
   which applies fair's own unit conversion. A network-marked test checks equality with `fill_from_rcmip`.
6. **Solar/Volcanic forcing** must be multiplied by each member's `forcing_scale[...]` manually
   (`fair` source: "forcing_scale has NO EFFECT on species provided as forcing"), as in FaIR's example.
7. **`override_defaults`** iterates over `self.configs`, so member subsets work with the full parameter file.

## File map

| File | Responsibility |
|---|---|
| `pyproject.toml`, `Makefile`, `.gitignore`, `LICENSE`, `CHANGELOG.md` | packaging and tooling |
| `src/goblin_fair/__init__.py` | public names, `__version__` |
| `src/goblin_fair/_data.py` | constants, bundled file paths, loaders, checksums |
| `src/goblin_fair/emissions.py` | `prepare_emissions` |
| `src/goblin_fair/engine.py` | `RunOutput`, `run_pair` |
| `src/goblin_fair/results.py` | `ContributionResult` |
| `src/goblin_fair/api.py` | `temperature_contribution`, `list_backgrounds` |
| `src/goblin_fair/data/*.csv`, `DATA_SOURCES.md` | bundled inputs + provenance |
| `scripts/build_data.py` | regenerate bundled data |
| `tests/…` | pytest suite (`slow`, `network` markers) |
| `README.md`, `CLAUDE.md`, `walkthrough/*.ipynb` | docs |

---

### Task 1: Project scaffold and tooling

**Files:** Create `pyproject.toml`, `Makefile`, `.gitignore`, `LICENSE`, `CHANGELOG.md`, `src/goblin_fair/__init__.py`, `tests/__init__.py` (empty), `tests/conftest.py`, `tests/test_package.py`.

**Interfaces:** Produces: `goblin_fair.__version__: str`; pytest markers `slow`, `network`.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[tool.poetry]
name = "goblin_fair"
version = "0.1.0"
description = "Simple, documented temperature-contribution calculations with the FaIR climate model"
authors = ["Colm Duffy <colm.p.duffy@gmail.com>"]
license = "GPL-3.0-only"
readme = "README.md"
packages = [{ include = "goblin_fair", from = "src" }]
include = [{ path = "src/goblin_fair/data/*", format = ["sdist", "wheel"] }]

[tool.poetry.dependencies]
python = ">=3.10,<4.0"
fair = "2.2.4"
pandas = ">=2.0"
numpy = ">=1.24"
matplotlib = ">=3.7"

[tool.poetry.group.test]
optional = true
[tool.poetry.group.test.dependencies]
pytest = "^8.0"
pytest-cov = "*"

[tool.poetry.group.dev]
optional = true
[tool.poetry.group.dev.dependencies]
jupyterlab = "*"
ipykernel = "*"
nbconvert = "*"
ruff = "*"

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
  "slow: runs FaIR (seconds each); excluded by `make test`",
  "network: downloads upstream data; excluded by `make test`",
]

[tool.ruff]
line-length = 88
target-version = "py310"
[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"
```

- [ ] **Step 2: Write `Makefile`**

```make
.PHONY: install test test-all lint format data walkthrough lab clean

install:
	poetry install --with test,dev

test:            ## fast tests only
	poetry run pytest -m "not slow and not network"

test-all:        ## everything, incl. real FaIR runs and upstream-data checks
	poetry run pytest

lint:
	poetry run ruff check src tests scripts

format:
	poetry run ruff format src tests scripts
	poetry run ruff check --fix src tests scripts

data:            ## rebuild bundled data from upstream sources (network)
	poetry run python scripts/build_data.py

walkthrough:     ## execute the walkthrough notebooks in place
	poetry run jupyter nbconvert --to notebook --execute --inplace \
		--ExecutePreprocessor.timeout=1200 walkthrough/*.ipynb

lab:
	poetry run jupyter lab walkthrough/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache dist
	find . -type d -name .ipynb_checkpoints -exec rm -rf {} +
```

- [ ] **Step 3: Write `.gitignore`** — Python/Jupyter/tool caches (as agrisyn) plus:

```gitignore
# Walkthrough notebooks are local learning material, not versioned
walkthrough/
# Claude Code project notes
CLAUDE.md
.claude/
```

- [ ] **Step 4: `LICENSE`** — copy GPL-3.0 text from `../agrisyn/LICENSE.md`. **`CHANGELOG.md`** — Keep a Changelog header with `## [Unreleased]`.

- [ ] **Step 5: Write failing test `tests/test_package.py`**

```python
import goblin_fair


def test_version_is_exposed():
    assert goblin_fair.__version__ == "0.1.0"
```

`tests/conftest.py` (grows in later tasks):

```python
"""Shared pytest fixtures for goblin_fair."""
```

- [ ] **Step 6:** `poetry install --with test,dev` then `poetry run pytest tests/test_package.py` → FAIL (`ModuleNotFoundError` or missing attribute).

- [ ] **Step 7: Write `src/goblin_fair/__init__.py`**

```python
"""goblin_fair: temperature contributions of emissions with the FaIR climate model."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("goblin_fair")
except PackageNotFoundError:  # running from a source tree without install
    __version__ = "0.1.0"

__all__ = ["__version__"]
```

- [ ] **Step 8:** `poetry run pytest tests/test_package.py` → PASS. `poetry run ruff check src tests` → clean.

- [ ] **Step 9: Commit** `chore: scaffold goblin_fair package with poetry, pytest and ruff` (include `poetry.lock`).

---

### Task 2: Bundled data, build script and provenance

**Files:** Create `scripts/build_data.py`, `src/goblin_fair/_data.py`, `src/goblin_fair/data/{4 CSVs}`, `src/goblin_fair/data/DATA_SOURCES.md`, `tests/test_data.py`.

**Interfaces:**
- Produces (`goblin_fair._data`):
  - `START_YEAR = 1750`, `MAX_END_YEAR = 2500`, `MIN_END_YEAR = 1902`
  - `CALIBRATION_VERSION = "1.4.1"`, `BACKGROUND_SOURCE = "RCMIP v5.1.0"`
  - `BACKGROUNDS: tuple[str, ...]` (the 8 SSPs)
  - `PARAMETERS_FILE, SPECIES_FILE, FORCING_FILE, BACKGROUND_FILE: str`; `DATA_FILES: tuple[str, ...]`
  - `data_path(name: str) -> pathlib.Path`
  - `file_sha256(path: Path) -> str`
  - `load_parameters(members: None | int | Sequence[int] = None) -> pd.DataFrame` (index = member id)
  - `load_forcing() -> pd.DataFrame` (index int year 1750–2500; columns `Solar`, `Volcanic`; W m-2)
  - `load_background(background: str) -> pd.DataFrame` (fair CSV format, `scenario` column first)

- [ ] **Step 1: Write `scripts/build_data.py`** (network; run once; outputs are committed)

```python
"""Rebuild goblin_fair's bundled data from upstream sources.

Every upstream file is downloaded to the pooch cache and verified against a
known hash before it is used. Outputs are written to src/goblin_fair/data/ and
their SHA-256 values printed for DATA_SOURCES.md. See that file for provenance.

Run: make data   (or: poetry run python scripts/build_data.py)
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pooch
from scipy.interpolate import interp1d

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from goblin_fair import _data  # noqa: E402

OUT = ROOT / "src" / "goblin_fair" / "data"

FAIR_COMMIT = "28572bb00e40d73f83f3365395fe8bc3a1b60bb9"
FAIR_BASE = (
    "https://raw.githubusercontent.com/OMS-NetZero/FAIR/"
    f"{FAIR_COMMIT}/examples/data/calibrated_constrained_ensemble/"
)
# upstream name -> (sha256, bundled name or None if transformed)
FAIR_FILES = {
    "calibrated_constrained_parameters_calibration1.4.1.csv": "<sha256 filled at step 2>",
    "species_configs_properties_calibration1.4.1.csv": "<sha256 filled at step 2>",
    "volcanic_solar.csv": "<sha256 filled at step 2>",
}
RCMIP_URL = (
    "https://rcmip-protocols-au.s3-ap-southeast-2.amazonaws.com/"
    "v5.1.0/rcmip-emissions-annual-means-v5-1-0.csv"
)
RCMIP_MD5 = "md5:4044106f55ca65b094670e7577eaf9b3"  # same hash fair 2.2.4 pins


def fetch_fair(name: str) -> Path:
    return Path(pooch.retrieve(FAIR_BASE + name, known_hash=f"sha256:{FAIR_FILES[name]}"))


def rcmip_name(specie: str) -> str:
    """FaIR species name -> RCMIP variable suffix (mirrors fair.io.fill_from_rcmip)."""
    special = {
        "CO2 FFI": "CO2|MAGICC Fossil and Industrial",
        "CO2 AFOLU": "CO2|MAGICC AFOLU",
    }
    return special.get(specie, specie.replace("-", ""))


def build_background(rcmip_csv: Path, species_csv: Path) -> pd.DataFrame:
    rc = pd.read_csv(rcmip_csv)
    rc = rc[(rc["Region"] == "World") & rc["Scenario"].isin(_data.BACKGROUNDS)]
    props = pd.read_csv(species_csv, index_col=0)
    species = props.index[props["input_mode"] == "emissions"]
    year_cols = [str(y) for y in range(1750, 2501)]
    rcmip_index = np.arange(1750.5, 2501.5)
    rows = []
    for scenario in _data.BACKGROUNDS:
        for specie in species:
            sel = rc[
                (rc["Scenario"] == scenario)
                & rc["Variable"].str.endswith("|" + rcmip_name(specie))
            ]
            if len(sel) != 1:
                raise RuntimeError(f"{scenario}/{specie}: expected 1 RCMIP row, got {len(sel)}")
            values = sel[year_cols].astype(float).interpolate(axis=1).to_numpy().squeeze()
            notnan = ~np.isnan(values)
            # identical to fill_from_rcmip: linear, extrapolated, on mid-year points
            values = interp1d(
                rcmip_index[notnan], values[notnan],
                fill_value="extrapolate", bounds_error=False,
            )(rcmip_index)
            row = {"scenario": scenario, "region": "World", "variable": specie,
                   "unit": sel["Unit"].iloc[0]}
            row.update({f"{t:.1f}": v for t, v in zip(rcmip_index, values)})
            rows.append(row)
    return pd.DataFrame(rows)


def build_forcing(volcanic_solar_csv: Path) -> pd.DataFrame:
    vs = pd.read_csv(volcanic_solar_csv, encoding="utf-8-sig")
    year_cols = [c for c in vs.columns if c not in ("Scenario", "Variable", "Region", "Unit")]
    years_in = np.array(year_cols, dtype=float)
    years_out = np.arange(_data.START_YEAR, _data.MAX_END_YEAR + 1)
    out = pd.DataFrame(index=pd.Index(years_out, name="year"))
    for var in ("Solar", "Volcanic"):
        block = vs.loc[vs["Variable"] == var, year_cols].astype(float)
        if not (block.nunique(axis=0) == 1).all():
            raise RuntimeError(f"{var} forcing differs between scenarios; cannot collapse")
        out[var] = np.interp(years_out, years_in, block.iloc[0].to_numpy())
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    params = fetch_fair("calibrated_constrained_parameters_calibration1.4.1.csv")
    species = fetch_fair("species_configs_properties_calibration1.4.1.csv")
    volc = fetch_fair("volcanic_solar.csv")
    rcmip = Path(pooch.retrieve(RCMIP_URL, known_hash=RCMIP_MD5))

    shutil.copyfile(params, OUT / _data.PARAMETERS_FILE)
    shutil.copyfile(species, OUT / _data.SPECIES_FILE)
    build_forcing(volc).to_csv(OUT / _data.FORCING_FILE)
    build_background(rcmip, species).to_csv(OUT / _data.BACKGROUND_FILE, index=False)

    print("| file | sha256 |\n|---|---|")
    for name in _data.DATA_FILES:
        print(f"| `{name}` | `{_data.file_sha256(OUT / name)}` |")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Pin upstream hashes.** Download the three FaIR files from the pinned commit URL, compute SHA-256 (`sha256sum`), and replace the three placeholders in `FAIR_FILES`. (The placeholder above exists only in this plan step; the committed script must contain real hashes.)

- [ ] **Step 3: Write failing tests `tests/test_data.py`**

```python
import re

import pandas as pd
import pytest

from goblin_fair import _data


def _recorded_checksums() -> dict[str, str]:
    text = _data.data_path("DATA_SOURCES.md").read_text(encoding="utf-8")
    return dict(re.findall(r"^\| `([\w.\-]+\.csv)` \| `([0-9a-f]{64})` \|$", text, re.M))


def test_every_bundled_file_is_documented_with_matching_sha256():
    recorded = _recorded_checksums()
    assert set(recorded) == set(_data.DATA_FILES)
    for name in _data.DATA_FILES:
        assert _data.file_sha256(_data.data_path(name)) == recorded[name], name


def test_load_parameters_all_members():
    p = _data.load_parameters()
    assert len(p) == 841
    assert "forcing_scale[Solar]" in p.columns


def test_load_parameters_first_n_members():
    p = _data.load_parameters(5)
    assert list(p.index) == list(_data.load_parameters().index[:5])


def test_load_parameters_explicit_members_keeps_order():
    ids = list(_data.load_parameters().index[[3, 0]])
    assert list(_data.load_parameters(ids).index) == ids


@pytest.mark.parametrize("bad", [0, 842, -1, [999_999_999], [], True, 2.5, "10"])
def test_load_parameters_rejects_invalid_members(bad):
    with pytest.raises(ValueError, match="members"):
        _data.load_parameters(bad)


def test_load_forcing_covers_run_period():
    f = _data.load_forcing()
    assert f.index[0] == 1750 and f.index[-1] == 2500
    assert list(f.columns) == ["Solar", "Volcanic"]
    assert not f.isna().any().any()


def test_load_background_is_fair_csv_format():
    bg = _data.load_background("ssp245")
    assert list(bg.columns[:4]) == ["scenario", "region", "variable", "unit"]
    assert set(bg["scenario"]) == {"ssp245"}
    assert {"CO2 FFI", "CO2 AFOLU", "CH4", "N2O", "Sulfur"} <= set(bg["variable"])
    assert bg.shape[0] == 51
    assert not bg.iloc[:, 4:].isna().any().any()


def test_load_background_rejects_unknown():
    with pytest.raises(ValueError, match="ssp245"):
        _data.load_background("ssp999")


def test_backgrounds_are_the_eight_ssps():
    assert _data.BACKGROUNDS == (
        "ssp119", "ssp126", "ssp245", "ssp370", "ssp434", "ssp460", "ssp534-over", "ssp585",
    )
```

- [ ] **Step 4:** `poetry run pytest tests/test_data.py` → FAIL (`ImportError: cannot import name '_data'`).

- [ ] **Step 5: Write `src/goblin_fair/_data.py`**

```python
"""Bundled model inputs: locations, loaders and checksums.

Provenance for every file is in data/DATA_SOURCES.md; rebuild with scripts/build_data.py.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

import pandas as pd

START_YEAR = 1750
MIN_END_YEAR = 1902  # the 1850-1900 baseline needs timebound 1901
MAX_END_YEAR = 2500

CALIBRATION_VERSION = "1.4.1"
BACKGROUND_SOURCE = "RCMIP v5.1.0"
BACKGROUNDS = (
    "ssp119", "ssp126", "ssp245", "ssp370", "ssp434", "ssp460", "ssp534-over", "ssp585",
)

PARAMETERS_FILE = "calibrated_constrained_parameters_1.4.1.csv"
SPECIES_FILE = "species_configs_properties_1.4.1.csv"
FORCING_FILE = "solar_volcanic_forcing.csv"
BACKGROUND_FILE = "background_emissions_rcmip_v5.1.0.csv"
DATA_FILES = (PARAMETERS_FILE, SPECIES_FILE, FORCING_FILE, BACKGROUND_FILE)

_DATA_DIR = Path(__file__).resolve().parent / "data"


def data_path(name: str) -> Path:
    """Absolute path of a bundled data file."""
    return _DATA_DIR / name


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def _all_parameters() -> pd.DataFrame:
    return pd.read_csv(data_path(PARAMETERS_FILE), index_col=0)


def load_parameters(members: None | int | Sequence[int] = None) -> pd.DataFrame:
    """Calibrated parameter sets, one row per ensemble member.

    members: None for all 841; an int N for the first N; or a sequence of member ids.
    """
    params = _all_parameters()
    if members is None:
        return params.copy()
    if isinstance(members, bool) or isinstance(members, (float, str)):
        raise ValueError(f"members must be None, an int or a list of member ids, got {members!r}")
    if isinstance(members, int):
        if not 1 <= members <= len(params):
            raise ValueError(f"members must be between 1 and {len(params)}, got {members}")
        return params.iloc[:members].copy()
    ids = list(members)
    if not ids:
        raise ValueError("members list is empty")
    unknown = [m for m in ids if m not in params.index]
    if unknown:
        raise ValueError(f"unknown members ids: {unknown[:5]}")
    return params.loc[ids].copy()


def load_forcing() -> pd.DataFrame:
    """Solar and volcanic effective radiative forcing (W m-2) on integer years."""
    return pd.read_csv(data_path(FORCING_FILE), index_col="year")


@lru_cache(maxsize=1)
def _all_backgrounds() -> pd.DataFrame:
    return pd.read_csv(data_path(BACKGROUND_FILE))


def load_background(background: str) -> pd.DataFrame:
    """Global emissions of every FaIR species for one SSP, in fair's CSV format."""
    if background not in BACKGROUNDS:
        raise ValueError(
            f"unknown background {background!r}; choose one of {', '.join(BACKGROUNDS)}"
        )
    df = _all_backgrounds()
    return df[df["scenario"] == background].reset_index(drop=True)
```

- [ ] **Step 6:** Run `make data`. Paste the printed checksum table into `DATA_SOURCES.md` (Step 7).

- [ ] **Step 7: Write `src/goblin_fair/data/DATA_SOURCES.md`** — sections: *Summary table*; one section per file with **Upstream** (URL/DOI, version, pinned commit), **Retrieved** (date), **Upstream checksum**, **Licence**, **Cite**, **Transformation**; *Licensing*; *Known caveats* (harmonisation note from spec §6); *How to rebuild*; and the machine-read table:

```markdown
## Checksums of bundled files

| file | sha256 |
|---|---|
| `calibrated_constrained_parameters_1.4.1.csv` | `<printed by build_data.py>` |
...
```

Before writing, confirm on the landing pages (Zenodo 10566813 and 4589756; GMD doi:10.5194/gmd-17-8569-2024, 10.5194/gmd-13-5175-2020, 10.5194/gmd-14-3007-2021) the title, authors, licence and year for each citation. Record only verified facts.

- [ ] **Step 8:** `poetry run pytest tests/test_data.py` → PASS.

- [ ] **Step 9: Commit** `feat: bundle FaIR v1.4.1 calibration and RCMIP v5.1.0 backgrounds with provenance`.

---

### Task 3: Emissions validation and unit conversion

**Files:** Create `src/goblin_fair/emissions.py`, `tests/test_emissions.py`.

**Interfaces:**
- Consumes: `_data.START_YEAR`.
- Produces: `prepare_emissions(emissions: pd.DataFrame, units: str | Mapping[str, str] = "kt", end_year: int = 2100) -> pd.DataFrame` — index `year` (int), columns FaIR species in `("CO2 FFI", "CO2 AFOLU", "CH4", "N2O")` order, values in FaIR units. Also `FAIR_UNITS: dict[str, str]`.

- [ ] **Step 1: Write failing tests `tests/test_emissions.py`**

```python
import numpy as np
import pandas as pd
import pytest

from goblin_fair.emissions import prepare_emissions


def frame(**cols):
    return pd.DataFrame(cols, index=pd.Index([2020, 2021], name="year"))


def test_kilotonnes_convert_to_fair_units():
    out = prepare_emissions(frame(CO2=[1000.0, 2000.0], CH4=[1000.0, 0.0], N2O=[1000.0, 0.0]))
    assert list(out.columns) == ["CO2 FFI", "CH4", "N2O"]
    np.testing.assert_allclose(out["CO2 FFI"], [1e-3, 2e-3])  # Gt CO2
    np.testing.assert_allclose(out["CH4"], [1.0, 0.0])  # Mt CH4
    np.testing.assert_allclose(out["N2O"], [1.0, 0.0])  # Mt N2O


@pytest.mark.parametrize("unit,factor", [("t", 1e-9), ("kt", 1e-6), ("Mt", 1e-3), ("Gt", 1.0)])
def test_co2_prefixes(unit, factor):
    out = prepare_emissions(frame(CO2=[1.0, 1.0]), units=unit)
    np.testing.assert_allclose(out["CO2 FFI"], factor)


def test_units_per_column_and_case_insensitive_names():
    out = prepare_emissions(frame(co2_ffi=[1.0, 1.0], Co2_Afolu=[1.0, 1.0], ch4=[1.0, 1.0]),
                            units={"CO2_FFI": "Gt", "co2_afolu": "Mt", "CH4": "kt"})
    assert list(out.columns) == ["CO2 FFI", "CO2 AFOLU", "CH4"]
    np.testing.assert_allclose(out["CO2 AFOLU"], 1e-3)
    np.testing.assert_allclose(out["CH4"], 1e-3)


def test_negative_values_allowed():
    out = prepare_emissions(frame(CO2=[-5.0, 1.0]), units="Gt")
    assert out["CO2 FFI"].iloc[0] == -5.0


def test_integer_like_index_accepted_and_output_index_is_int():
    df = pd.DataFrame({"CH4": [1.0]}, index=[2030.0])
    assert prepare_emissions(df).index.tolist() == [2030]


@pytest.mark.parametrize(
    "df,units,match",
    [
        (frame(CO2=[1.0, 1.0], CO2_FFI=[1.0, 1.0]), "kt", "CO2"),
        (frame(CO2e=[1.0, 1.0]), "kt", "gas-specific"),
        (frame(CO2=[1.0, 1.0]), "kt CO2e", "gas-specific"),
        (frame(CO2=[1.0, 1.0]), {"CO2": "GWP100"}, "gas-specific"),
        (frame(SF6=[1.0, 1.0]), "kt", "SF6"),
        (frame(CO2=[1.0, np.nan]), "kt", "2021"),
        (frame(CO2=["a", "b"]), "kt", "numeric"),
        (frame(CO2=[1.0, 1.0]), "mt", "units"),
        (frame(CO2=[1.0, 1.0]), {"CH4": "kt"}, "CO2"),
        (frame(co2=[1.0, 1.0], CO2=[1.0, 1.0]), "kt", "duplicate"),
        (pd.DataFrame(), "kt", "at least one"),
    ],
)
def test_invalid_inputs_raise(df, units, match):
    with pytest.raises(ValueError, match=match):
        prepare_emissions(df, units=units)


@pytest.mark.parametrize(
    "index,match",
    [
        ([2021, 2020], "increasing"),
        ([2020, 2020], "increasing"),
        ([2020.5, 2021.0], "whole years"),
        ([1749, 1750], "1750"),
        ([2099, 2100], "2099"),
    ],
)
def test_invalid_years_raise(index, match):
    df = pd.DataFrame({"CH4": [1.0, 1.0]}, index=index)
    with pytest.raises(ValueError, match=match):
        prepare_emissions(df, end_year=2100)


def test_gap_in_years_warns():
    df = pd.DataFrame({"CH4": [1.0, 1.0]}, index=[2020, 2025])
    with pytest.warns(UserWarning, match="zero"):
        prepare_emissions(df)
```

- [ ] **Step 2:** `poetry run pytest tests/test_emissions.py` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `src/goblin_fair/emissions.py`**

```python
"""Validate user emissions and convert them to the species and units FaIR expects."""

from __future__ import annotations

import re
import warnings
from collections.abc import Mapping

import numpy as np
import pandas as pd

from goblin_fair._data import START_YEAR

# user column (upper-cased) -> FaIR species
_COLUMN_TO_SPECIE = {
    "CO2": "CO2 FFI",
    "CO2_FFI": "CO2 FFI",
    "CO2_AFOLU": "CO2 AFOLU",
    "CH4": "CH4",
    "N2O": "N2O",
}
_SPECIE_ORDER = ("CO2 FFI", "CO2 AFOLU", "CH4", "N2O")
FAIR_UNITS = {
    "CO2 FFI": "Gt CO2/yr",
    "CO2 AFOLU": "Gt CO2/yr",
    "CH4": "Mt CH4/yr",
    "N2O": "Mt N2O/yr",
}
_TONNES = {"t": 1.0, "kt": 1e3, "Mt": 1e6, "Gt": 1e9}
_EQUIVALENT = re.compile(r"co2[\s_-]*e|gwp", re.IGNORECASE)
_EQUIVALENT_MSG = (
    "goblin_fair needs gas-specific emissions (mass of CO2, CH4 and N2O separately), "
    "not CO2-equivalent / GWP-weighted totals. FaIR models each gas's own lifetime "
    "and warming effect."
)


def prepare_emissions(
    emissions: pd.DataFrame,
    units: str | Mapping[str, str] = "kt",
    end_year: int = 2100,
) -> pd.DataFrame:
    """Return emissions indexed by year with FaIR species columns in FaIR units.

    Columns (case-insensitive): CO2, or CO2_FFI and/or CO2_AFOLU; CH4; N2O.
    Values are the mass of the gas itself per year. `units` is one of
    t / kt / Mt / Gt, or a dict of those per column. Years must be whole,
    strictly increasing and within 1750..end_year-1. Missing years inside the
    range are treated as zero additional emissions.
    """
    if not isinstance(emissions, pd.DataFrame) or emissions.shape[1] == 0:
        raise ValueError("emissions must be a DataFrame with at least one gas column")

    names = {str(c): str(c).strip().upper() for c in emissions.columns}
    for original in names:
        if _EQUIVALENT.search(original):
            raise ValueError(f"column {original!r}: {_EQUIVALENT_MSG}")
    normalised = list(names.values())
    dupes = sorted({n for n in normalised if normalised.count(n) > 1})
    if dupes:
        raise ValueError(f"duplicate columns after ignoring case: {dupes}")
    unknown = [o for o, n in names.items() if n not in _COLUMN_TO_SPECIE]
    if unknown:
        raise ValueError(
            f"unsupported columns {unknown}; use CO2 (or CO2_FFI / CO2_AFOLU), CH4, N2O"
        )
    if "CO2" in normalised and {"CO2_FFI", "CO2_AFOLU"} & set(normalised):
        raise ValueError("give either CO2 or CO2_FFI/CO2_AFOLU, not both")

    unit_for = _resolve_units(units, names)
    years = _validate_years(emissions.index, end_year)

    out = pd.DataFrame(index=pd.Index(years, name="year"))
    for original, name in names.items():
        column = emissions[original] if original in emissions else emissions[_find(emissions, original)]
        if not pd.api.types.is_numeric_dtype(column) or pd.api.types.is_bool_dtype(column):
            raise ValueError(f"column {original!r} must be numeric")
        values = column.to_numpy(dtype=float)
        if np.isnan(values).any():
            bad = int(years[np.isnan(values)][0])
            raise ValueError(f"column {original!r} has a missing value in year {bad}")
        specie = _COLUMN_TO_SPECIE[name]
        target = FAIR_UNITS[specie].split()[0]
        out[specie] = values * _TONNES[unit_for[name]] / _TONNES[target]
    return out[[s for s in _SPECIE_ORDER if s in out.columns]]


def _find(df: pd.DataFrame, label: str):
    return next(c for c in df.columns if str(c) == label)


def _resolve_units(units: str | Mapping[str, str], names: dict[str, str]) -> dict[str, str]:
    if isinstance(units, str):
        mapping = {n: units for n in names.values()}
    else:
        mapping = {str(k).strip().upper(): v for k, v in units.items()}
        missing = [n for n in names.values() if n not in mapping]
        if missing:
            raise ValueError(f"units not given for columns {missing}")
    for name, unit in mapping.items():
        if _EQUIVALENT.search(str(unit)):
            raise ValueError(f"units for {name!r}: {_EQUIVALENT_MSG}")
        if unit not in _TONNES:
            raise ValueError(f"units for {name!r} must be one of t, kt, Mt, Gt; got {unit!r}")
    return mapping


def _validate_years(index: pd.Index, end_year: int) -> np.ndarray:
    raw = np.asarray(index, dtype=float)
    if np.any(raw != np.round(raw)):
        raise ValueError("emissions index must be whole years")
    years = raw.astype(int)
    if np.any(np.diff(years) <= 0):
        raise ValueError("emissions years must be strictly increasing with no duplicates")
    last = end_year - 1
    if years[0] < START_YEAR or years[-1] > last:
        raise ValueError(
            f"emissions years must be within {START_YEAR}..{last} "
            f"(emissions in a year first affect temperature at the start of the next year; "
            f"raise end_year to include later years)"
        )
    if len(years) > 1 and np.any(np.diff(years) > 1):
        warnings.warn(
            "emissions years have gaps; missing years are treated as zero additional "
            "emissions (no interpolation)",
            UserWarning,
            stacklevel=3,
        )
    return years
```

(Simplify `column = …` to `emissions.iloc[:, i]` enumeration during implementation if cleaner — behaviour must stay the same.)

- [ ] **Step 4:** `poetry run pytest tests/test_emissions.py` → PASS. `make lint` clean.

- [ ] **Step 5: Commit** `feat: validate emissions input and convert to FaIR units`.

---

### Task 4: Result object

**Files:** Create `src/goblin_fair/results.py`, `tests/test_results.py`.

**Interfaces:**
- Produces: `ContributionResult(years: np.ndarray, members: np.ndarray, background_temperature: np.ndarray, perturbed_temperature: np.ndarray, metadata: dict)` (frozen dataclass; temperature arrays shape `(n_years, n_members)`, K, surface layer) with
  `ensemble -> pd.DataFrame`, `summary(quantiles=(0.05, 0.5, 0.95)) -> pd.DataFrame`,
  `background_warming(quantiles=(0.05, 0.5, 0.95)) -> pd.DataFrame`, `plot(ax=None) -> matplotlib.axes.Axes`.

- [ ] **Step 1: Write failing tests `tests/test_results.py`**

```python
import matplotlib

matplotlib.use("Agg")
import numpy as np
import pytest

from goblin_fair.results import ContributionResult


@pytest.fixture
def result():
    years = np.arange(1750, 2101)
    members = np.array([10, 20, 30, 40, 50])
    rng = np.random.default_rng(0)
    background = rng.normal(size=(years.size, members.size))
    contribution = np.outer(np.linspace(0, 1, years.size), [1.0, 2.0, 3.0, 4.0, 5.0])
    return ContributionResult(years, members, background, background + contribution, {"background": "ssp245"})


def test_ensemble_is_member_wise_difference(result):
    ens = result.ensemble
    assert ens.shape == (351, 5)
    assert list(ens.columns) == [10, 20, 30, 40, 50]
    assert ens.index.name == "year"
    np.testing.assert_allclose(ens.loc[2100].to_numpy(), [1, 2, 3, 4, 5])


def test_summary_default_quantiles(result):
    s = result.summary()
    assert list(s.columns) == ["p5", "p50", "p95"]
    np.testing.assert_allclose(s.loc[2100, "p50"], 3.0)
    np.testing.assert_allclose(s.loc[2100, "p5"], np.quantile([1, 2, 3, 4, 5], 0.05))


def test_summary_custom_quantile_labels(result):
    assert list(result.summary((0.025, 0.17, 0.5)).columns) == ["p2.5", "p17", "p50"]


@pytest.mark.parametrize("bad", [(), (1.5,), (-0.1,)])
def test_summary_rejects_bad_quantiles(result, bad):
    with pytest.raises(ValueError, match="quantiles"):
        result.summary(bad)


def test_background_warming_relative_to_1850_1900():
    years = np.arange(1750, 2101)
    temps = np.where(years >= 1850, 1.0, 0.0)[:, None].repeat(3, axis=1)
    temps[years > 1901] = 2.0
    r = ContributionResult(years, np.arange(3), temps, temps, {})
    bw = r.background_warming()
    np.testing.assert_allclose(bw.loc[2000, "p50"], 1.0)
    # weighted mean over timebounds 1850..1901 of a constant 1.0 is 1.0
    np.testing.assert_allclose(bw.loc[1900, "p50"], 0.0)


def test_plot_returns_axes(result):
    ax = result.plot()
    assert ax.get_ylabel().startswith("Temperature")
    assert len(ax.lines) == 1
```

- [ ] **Step 2:** `poetry run pytest tests/test_results.py` → FAIL.

- [ ] **Step 3: Write `src/goblin_fair/results.py`**

```python
"""The object returned by temperature_contribution."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

DEFAULT_QUANTILES = (0.05, 0.5, 0.95)


@dataclass(frozen=True)
class ContributionResult:
    """Temperature contribution of a set of emissions, for every ensemble member.

    Year Y is the global mean surface temperature at the start of year Y (FaIR
    'timebounds'). All temperatures are in kelvin (= degrees C of change).
    """

    years: np.ndarray
    members: np.ndarray
    background_temperature: np.ndarray
    perturbed_temperature: np.ndarray
    metadata: dict = field(default_factory=dict)

    @property
    def ensemble(self) -> pd.DataFrame:
        """Contribution (perturbed minus background) per year and member, K."""
        return self._frame(self.perturbed_temperature - self.background_temperature)

    def summary(self, quantiles: Sequence[float] = DEFAULT_QUANTILES) -> pd.DataFrame:
        """Quantiles across members of the contribution, K. Default: 5th, 50th, 95th."""
        return _quantile_frame(self.ensemble, quantiles)

    def background_warming(self, quantiles: Sequence[float] = DEFAULT_QUANTILES) -> pd.DataFrame:
        """Background scenario warming relative to each member's 1850-1900 mean, K."""
        temps = self.background_temperature
        in_base = (self.years >= 1850) & (self.years <= 1901)
        weights = np.ones(in_base.sum())
        weights[[0, -1]] = 0.5  # timebounds -> annual means for 1850..1900
        baseline = np.average(temps[in_base], axis=0, weights=weights)
        return _quantile_frame(self._frame(temps - baseline), quantiles)

    def plot(self, ax=None, color: str = "C0"):
        """Median contribution with the 5-95 % range shaded. Returns the Axes."""
        import matplotlib.pyplot as plt

        if ax is None:
            _, ax = plt.subplots(figsize=(8, 4.5))
        s = self.summary()
        ax.fill_between(s.index, s["p5"], s["p95"], color=color, alpha=0.25, lw=0,
                        label="5-95 % range")
        ax.plot(s.index, s["p50"], color=color, label="median")
        ax.axhline(0, color="0.6", lw=0.8)
        ax.set_xlabel("Year")
        ax.set_ylabel("Temperature contribution (K)")
        bg = self.metadata.get("background")
        ax.set_title(f"Temperature contribution vs {bg} background" if bg else
                     "Temperature contribution")
        ax.legend(frameon=False)
        return ax

    def _frame(self, values: np.ndarray) -> pd.DataFrame:
        return pd.DataFrame(values, index=pd.Index(self.years, name="year"),
                            columns=pd.Index(self.members, name="member"))


def _quantile_frame(frame: pd.DataFrame, quantiles: Sequence[float]) -> pd.DataFrame:
    qs = list(quantiles)
    if not qs or any(not 0 <= q <= 1 for q in qs):
        raise ValueError(f"quantiles must be a non-empty sequence of values in [0, 1], got {quantiles!r}")
    values = np.quantile(frame.to_numpy(), qs, axis=1).T
    return pd.DataFrame(values, index=frame.index, columns=[f"p{q * 100:g}" for q in qs])
```

- [ ] **Step 4:** `poetry run pytest tests/test_results.py` → PASS.

- [ ] **Step 5: Commit** `feat: add ContributionResult with summary, ensemble and plot`.

---

### Task 5: FaIR engine and public API

**Files:** Create `src/goblin_fair/engine.py`, `src/goblin_fair/api.py`, `tests/test_engine.py`, `tests/test_api.py`; modify `src/goblin_fair/__init__.py`, `tests/conftest.py`.

**Interfaces:**
- Consumes: `_data.*`, `prepare_emissions`, `ContributionResult`.
- Produces:
  - `engine.RunOutput(years: np.ndarray, members: np.ndarray, background: np.ndarray, perturbed: np.ndarray)` (frozen dataclass, arrays `(n_years, n_members)`)
  - `engine.run_pair(emissions: pd.DataFrame, background: str, end_year: int, members=None) -> RunOutput` — `emissions` as returned by `prepare_emissions`.
  - `api.temperature_contribution(emissions, units="kt", background="ssp245", end_year=2100, members=None) -> ContributionResult`
  - `api.list_backgrounds() -> list[str]`
  - Package exports: `temperature_contribution`, `ContributionResult`, `list_backgrounds`, `__version__`.

- [ ] **Step 1: Write failing fast tests `tests/test_api.py`**

```python
import pandas as pd
import pytest

import goblin_fair as gf


def test_public_names():
    assert set(gf.__all__) == {"temperature_contribution", "ContributionResult",
                               "list_backgrounds", "__version__"}


def test_list_backgrounds():
    assert gf.list_backgrounds() == ["ssp119", "ssp126", "ssp245", "ssp370",
                                     "ssp434", "ssp460", "ssp534-over", "ssp585"]


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"background": "rcp45"}, "ssp245"),
        ({"end_year": 1901}, "1902"),
        ({"end_year": 2501}, "2500"),
        ({"end_year": 2100.0}, "end_year"),
        ({"members": 0}, "members"),
    ],
)
def test_invalid_arguments_fail_before_running_fair(kwargs, match):
    df = pd.DataFrame({"CH4": [1.0]}, index=[2030])
    with pytest.raises(ValueError, match=match):
        gf.temperature_contribution(df, **kwargs)
```

- [ ] **Step 2: Write failing slow tests `tests/test_engine.py`** and extend `tests/conftest.py`

`tests/conftest.py`:

```python
"""Shared pytest fixtures for goblin_fair."""

import pandas as pd
import pytest

import goblin_fair as gf

N_MEMBERS = 5


@pytest.fixture(scope="session")
def co2_pulse_result():
    """10 Gt CO2/yr for 2030-2039 on ssp245, 5 members, to 2080."""
    df = pd.DataFrame({"CO2": 10.0}, index=range(2030, 2040))
    return gf.temperature_contribution(df, units="Gt", end_year=2080, members=N_MEMBERS)
```

`tests/test_engine.py`:

```python
import numpy as np
import pandas as pd
import pytest

import goblin_fair as gf

pytestmark = pytest.mark.slow
N = 5


def test_zero_emissions_give_zero_contribution():
    df = pd.DataFrame({"CO2": 0.0, "CH4": 0.0, "N2O": 0.0}, index=range(2020, 2050))
    res = gf.temperature_contribution(df, end_year=2060, members=N)
    np.testing.assert_allclose(res.ensemble.to_numpy(), 0.0, atol=1e-12)


def test_co2_pulse_no_effect_before_and_warming_after(co2_pulse_result):
    ens = co2_pulse_result.ensemble
    np.testing.assert_allclose(ens.loc[:2030].to_numpy(), 0.0, atol=1e-12)
    assert (ens.loc[2031:] > 0).all().all()
    assert ens.shape == (2080 - 1750 + 1, N)


def test_contribution_scales_nearly_linearly(co2_pulse_result):
    df = pd.DataFrame({"CO2": 20.0}, index=range(2030, 2040))
    double = gf.temperature_contribution(df, units="Gt", end_year=2080, members=N)
    ratio = double.ensemble.loc[2080] / co2_pulse_result.ensemble.loc[2080]
    assert ((ratio > 1.9) & (ratio < 2.1)).all()


def test_methane_response_decays_faster_than_co2(co2_pulse_result):
    df = pd.DataFrame({"CH4": 300.0}, index=range(2030, 2040))
    ch4 = gf.temperature_contribution(df, units="Mt", end_year=2080, members=N).summary()["p50"]
    co2 = co2_pulse_result.summary()["p50"]
    assert ch4.loc[2080] / ch4.max() < co2.loc[2080] / co2.max()


def test_result_metadata_and_background(co2_pulse_result):
    md = co2_pulse_result.metadata
    assert md["fair_version"] == "2.2.4"
    assert md["calibration"] == "1.4.1"
    assert md["background"] == "ssp245"
    assert md["n_members"] == N
    bw = co2_pulse_result.background_warming()
    assert 0.5 < bw.loc[2020, "p50"] < 2.0


@pytest.mark.network
def test_bundled_background_matches_fill_from_rcmip():
    from fair import FAIR
    from fair.io import read_properties

    from goblin_fair import _data

    def allocated():
        f = FAIR(ch4_method="Thornhill2021")
        f.define_time(1750, 2100, 1)
        f.define_scenarios(["ssp245"])
        f.define_configs(list(_data.load_parameters(2).index))
        species, props = read_properties(filename=str(_data.data_path(_data.SPECIES_FILE)))
        f.define_species(species, props)
        f.allocate()
        return f

    ours, theirs = allocated(), allocated()
    ours.fill_from_pandas("emissions", _data.load_background("ssp245"))
    theirs.fill_from_rcmip()
    np.testing.assert_allclose(ours.emissions.to_numpy(), theirs.emissions.to_numpy(),
                               rtol=1e-9, atol=0)
```

- [ ] **Step 3:** `poetry run pytest tests/test_api.py tests/test_engine.py` → FAIL (`AttributeError: temperature_contribution`).

- [ ] **Step 4: Write `src/goblin_fair/engine.py`**

```python
"""The only module that talks to fair.

Runs one FaIR instance with two scenarios that share everything except the user's
emissions: 'background' (an SSP) and 'perturbed' (the SSP plus the user's emissions).
Recipe follows FaIR's calibrated, constrained ensemble example (fair 2.2.4).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from fair import FAIR
from fair.interface import fill, initialise
from fair.io import read_properties

from goblin_fair import _data

SCENARIOS = ("background", "perturbed")


@dataclass(frozen=True)
class RunOutput:
    years: np.ndarray
    members: np.ndarray
    background: np.ndarray  # surface temperature, K, shape (n_years, n_members)
    perturbed: np.ndarray


def run_pair(
    emissions: pd.DataFrame,
    background: str,
    end_year: int,
    members: None | int | Sequence[int] = None,
) -> RunOutput:
    params = _data.load_parameters(members)
    species_file = str(_data.data_path(_data.SPECIES_FILE))

    f = FAIR(ch4_method="Thornhill2021")
    f.define_time(_data.START_YEAR, end_year, 1)
    f.define_scenarios(list(SCENARIOS))
    f.define_configs(list(params.index))
    species, properties = read_properties(filename=species_file)
    f.define_species(species, properties)
    f.allocate()

    # 1. background emissions of every species, identical in both scenarios
    bg = _data.load_background(background)
    both = []
    for name in SCENARIOS:
        copy = bg.copy()
        copy["scenario"] = name
        both.append(copy)
    f.fill_from_pandas("emissions", pd.concat(both, ignore_index=True))

    # 2. add the user's emissions to the perturbed scenario (year Y -> timepoint Y+0.5)
    timepoints = emissions.index.to_numpy(dtype=float) + 0.5
    for specie in emissions.columns:
        selection = dict(specie=specie, scenario="perturbed", timepoints=timepoints)
        current = f.emissions.loc[selection]
        fill(f.emissions, current + emissions[specie].to_numpy()[:, None], **selection)

    # 3. natural forcing, scaled per member (fair ignores forcing_scale for input forcing)
    forcing = _data.load_forcing().loc[_data.START_YEAR : end_year]
    for specie in ("Solar", "Volcanic"):
        scaled = (forcing[specie].to_numpy()[:, None, None]
                  * params[f"forcing_scale[{specie}]"].to_numpy()[None, None, :])
        fill(f.forcing, scaled, specie=specie)

    # 4. calibrated parameters
    f.fill_species_configs(species_file)
    f.override_defaults(str(_data.data_path(_data.PARAMETERS_FILE)))

    # 5. pre-industrial initial state, then run
    initialise(f.concentration, f.species_configs["baseline_concentration"])
    initialise(f.forcing, 0)
    initialise(f.temperature, 0)
    initialise(f.cumulative_emissions, 0)
    initialise(f.airborne_emissions, 0)
    initialise(f.ocean_heat_content_change, 0)
    f.run(progress=False)

    surface = f.temperature.sel(layer=0).transpose("timebounds", "scenario", "config")
    return RunOutput(
        years=f.timebounds.astype(int),
        members=np.asarray(params.index),
        background=surface.sel(scenario="background").to_numpy(),
        perturbed=surface.sel(scenario="perturbed").to_numpy(),
    )


def fair_version() -> str:
    import fair

    return fair.__version__
```

Note: if `initialise(f.forcing, 0)` after step 3 overwrites the first timebound of Solar/Volcanic, that matches FaIR's example (initialise only sets the first timebound). Verify by reading `fair.interface.initialise` during implementation.

- [ ] **Step 5: Write `src/goblin_fair/api.py`**

```python
"""Public entry points."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

import pandas as pd

from goblin_fair import __version__, _data, engine
from goblin_fair.emissions import FAIR_UNITS, prepare_emissions
from goblin_fair.results import ContributionResult


def list_backgrounds() -> list[str]:
    """Names of the background scenarios available (RCMIP v5.1.0 SSPs)."""
    return list(_data.BACKGROUNDS)


def temperature_contribution(
    emissions: pd.DataFrame,
    units: str | Mapping[str, str] = "kt",
    background: str = "ssp245",
    end_year: int = 2100,
    members: None | int | Sequence[int] = None,
) -> ContributionResult:
    """Global surface temperature change caused by `emissions`.

    Runs the FaIR calibrated ensemble twice in one go — the background SSP alone
    and the background plus `emissions` — and returns the difference for every
    ensemble member.

    Parameters
    ----------
    emissions : DataFrame indexed by year, columns CO2 (or CO2_FFI/CO2_AFOLU), CH4, N2O.
        Mass of each gas per year. Years missing from the index count as zero.
    units : "t", "kt", "Mt" or "Gt", or a dict of those per column.
    background : one of list_backgrounds(); default "ssp245" (SSP2-4.5).
    end_year : last year simulated, 1902..2500.
    members : None for all 841 ensemble members, an int N for the first N, or a list of ids.
    """
    if background not in _data.BACKGROUNDS:
        raise ValueError(
            f"unknown background {background!r}; choose one of {', '.join(_data.BACKGROUNDS)}"
        )
    if isinstance(end_year, bool) or not isinstance(end_year, int):
        raise ValueError(f"end_year must be an int, got {end_year!r}")
    if not _data.MIN_END_YEAR <= end_year <= _data.MAX_END_YEAR:
        raise ValueError(
            f"end_year must be between {_data.MIN_END_YEAR} and {_data.MAX_END_YEAR}, got {end_year}"
        )
    prepared = prepare_emissions(emissions, units=units, end_year=end_year)
    _data.load_parameters(members)  # validate before the expensive run

    out = engine.run_pair(prepared, background, end_year, members)
    metadata = {
        "goblin_fair_version": __version__,
        "fair_version": engine.fair_version(),
        "calibration": _data.CALIBRATION_VERSION,
        "background": background,
        "background_source": _data.BACKGROUND_SOURCE,
        "end_year": end_year,
        "n_members": len(out.members),
        "species": {s: FAIR_UNITS[s] for s in prepared.columns},
        "input_units": units if isinstance(units, str) else dict(units),
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return ContributionResult(out.years, out.members, out.background, out.perturbed, metadata)
```

- [ ] **Step 6: Update `src/goblin_fair/__init__.py`**

```python
"""goblin_fair: temperature contributions of emissions with the FaIR climate model."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("goblin_fair")
except PackageNotFoundError:  # running from a source tree without install
    __version__ = "0.1.0"

from goblin_fair.api import list_backgrounds, temperature_contribution  # noqa: E402
from goblin_fair.results import ContributionResult  # noqa: E402

__all__ = ["temperature_contribution", "ContributionResult", "list_backgrounds", "__version__"]
```

- [ ] **Step 7:** `make test` → PASS (fast). `make test-all` → PASS (slow + network). If
  `test_zero_emissions_give_zero_contribution` fails, **stop**: noise is not shared between
  scenarios; investigate before changing tolerances.

- [ ] **Step 8: Performance check.** Time `temperature_contribution` with all 841 members, 2025–2050 toy emissions, end_year 2100. Must be < 60 s (spec §9.2). Record the time in CHANGELOG.

- [ ] **Step 9: Commit** `feat: add FaIR engine and temperature_contribution API`.

---

### Task 6: Documentation — README, CLAUDE.md, CHANGELOG

**Files:** Create `README.md`, `CLAUDE.md` (git-ignored); modify `CHANGELOG.md`.

- [ ] **Step 1: `README.md`** with, in order:
  - Title + badges (static shields.io):
    `python-3.10%2B-blue`, `license-GPL--3.0-blue` → LICENSE, `packaging-poetry-1e293b`,
    `FaIR-2.2.4-2c7fb8` → pypi.org/project/fair/2.2.4, `calibration-v1.4.1-41ab5d` → doi.org/10.5281/zenodo.10566813,
    `tests-pytest-brightgreen` → tests/, `code%20style-ruff-261230` → ruff, `version-0.1.0-orange` → CHANGELOG.md.
    Repository links use `https://github.com/colmduff/goblin_fair`.
  - One-paragraph what/why; FORESIGHT context (sibling of goblin_lite, agrisyn).
  - Install (`poetry install`, `pip install git+…`).
  - Quickstart (the toy example; output shape).
  - How it works (marginal method in 5 lines; ensemble; year convention; gas-specific inputs; no CO2e).
  - Data sources & citations (table from DATA_SOURCES.md summary + link to it; full citation list).
  - Caveats (harmonisation, CO2 total treated as fossil, stochastic variability, no F-gases/aerosols in inputs).
  - Development (`make install/test/test-all/lint/data/walkthrough`; walkthrough folder is local/git-ignored).
  - Roadmap (objective 2 Ireland, objective 3 EU and other countries; per-gas attribution).
  - Licence (code GPL-3.0; data per upstream).
- [ ] **Step 2: `CLAUDE.md`** — purpose + 3 objectives; decisions table; module map + "only engine.py imports fair"; data rule (no bundled data without DATA_SOURCES.md entry + checksum + build_data.py path); conventions (TDD, `make test` before commit, slow/network markers, commit trailer); walkthrough is git-ignored; pointers to spec and plan.
- [ ] **Step 3:** CHANGELOG `## [0.1.0] - 2026-09-15` Added list.
- [ ] **Step 4:** `git status` must not list `CLAUDE.md`. Commit `docs: add README with badges and changelog`.

---

### Task 7: Walkthrough notebooks (git-ignored)

**Files:** Create `walkthrough/01_quickstart.ipynb`, `walkthrough/02_how_it_works.ipynb`, `walkthrough/README.md`.

- [ ] **Step 1:** Write notebooks (markdown-led, short code cells):
  - **01_quickstart:** what the package answers; build `emissions` (2025–2050: CO2 10 Mt, CH4 0.5 Mt, N2O 0.02 Mt per year, units "Mt"); `gf.temperature_contribution(emissions, units="Mt")`; `res.summary().loc[[2030, 2050, 2075, 2100]]` shown in mK; `res.plot()`; reading median and 5–95 %; `res.metadata`.
  - **02_how_it_works:** background vs perturbed absolute warming (median lines) and the difference; ensemble spaghetti (`res.ensemble`); CO2 vs CH4 response shapes for equal-length pulses (normalised by peak); where the data comes from (render `DATA_SOURCES.md` summary via `IPython.display.Markdown`); caveats.
- [ ] **Step 2:** `make walkthrough` → both execute without error.
- [ ] **Step 3:** `git status --ignored` shows `walkthrough/` as ignored. No commit of notebooks.

---

### Task 8: Final verification

- [ ] `make lint` clean; `make test` and `make test-all` pass (report counts).
- [ ] Fresh-install check: `poetry build` then install the wheel into a temp venv and run a 5-member call from outside the repo (confirms data ships in the wheel).
- [ ] Spec §9 success criteria checked one by one; record results in the final report.
- [ ] Commit any fixes.
