"""The only module in goblin_fair that talks to fair.

One FaIR instance runs two scenarios that share everything except the user's
emissions: "background" (an SSP) and "perturbed" (the same SSP plus the user's
emissions). The recipe follows FaIR's calibrated, constrained ensemble example
for fair 2.2.4.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import fair
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


def fair_version() -> str:
    return fair.__version__


def run_pair(
    emissions: pd.DataFrame,
    background: str,
    end_year: int,
    members: None | int | Sequence[int] = None,
) -> RunOutput:
    """Run background and background+emissions for the chosen ensemble members.

    `emissions` must already be in FaIR species and units, as returned by
    goblin_fair.emissions.prepare_emissions.
    """
    params = _data.load_parameters(members)
    species_file = str(_data.data_path(_data.SPECIES_FILE))

    f = FAIR(ch4_method="Thornhill2021")
    f.define_time(_data.START_YEAR, end_year, 1)
    f.define_scenarios(list(SCENARIOS))
    f.define_configs(list(params.index))
    species, properties = read_properties(filename=species_file)
    f.define_species(species, properties)
    f.allocate()

    # 1. Background emissions of every species, identical in both scenarios.
    #    fill_from_pandas applies fair's own unit conversion.
    bg = _data.load_background(background)
    per_scenario = [bg.assign(scenario=name) for name in SCENARIOS]
    f.fill_from_pandas("emissions", pd.concat(per_scenario, ignore_index=True))

    # 2. Add the user's emissions to the perturbed scenario.
    #    Emissions in year Y sit on FaIR timepoint Y + 0.5.
    timepoints = emissions.index.to_numpy(dtype=float) + 0.5
    for specie in emissions.columns:
        selection = dict(specie=specie, scenario="perturbed", timepoints=timepoints)
        current = f.emissions.loc[selection].to_numpy()
        fill(f.emissions, current + emissions[specie].to_numpy()[:, None], **selection)

    # 3. Solar and volcanic forcing, scaled per member. fair does not apply
    #    forcing_scale to species supplied as forcing, so do it here.
    forcing = _data.load_forcing().loc[_data.START_YEAR : end_year]
    for specie in ("Solar", "Volcanic"):
        scale = params[f"forcing_scale[{specie}]"].to_numpy()
        scaled = forcing[specie].to_numpy()[:, None, None] * scale[None, None, :]
        fill(f.forcing, scaled, specie=specie)

    # 4. Calibrated species configs and per-member parameters.
    f.fill_species_configs(species_file)
    f.override_defaults(str(_data.data_path(_data.PARAMETERS_FILE)))

    # 5. Pre-industrial initial state, then run.
    initialise(f.concentration, f.species_configs["baseline_concentration"])
    initialise(f.forcing, 0)
    initialise(f.temperature, 0)
    initialise(f.cumulative_emissions, 0)
    initialise(f.airborne_emissions, 0)
    initialise(f.ocean_heat_content_change, 0)
    f.run(progress=False)

    surface = f.temperature.sel(layer=0).transpose("timebounds", "scenario", "config")
    return RunOutput(
        years=np.asarray(f.timebounds).astype(int),
        members=np.asarray(params.index),
        background=surface.sel(scenario="background").to_numpy(),
        perturbed=surface.sel(scenario="perturbed").to_numpy(),
    )
