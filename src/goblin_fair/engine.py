"""The only module in goblin_fair that talks to fair.

One FaIR instance runs two scenarios that share everything except the user's
emissions, "with" and "without" them:

- leave_one_out: "with" is the SSP (the real world, which already contains the
  emitter), "without" is the SSP minus the user's emissions.
- add: "with" is the SSP plus the user's emissions, "without" is the SSP.

The recipe follows FaIR's calibrated, constrained ensemble example for fair 2.2.4.
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
from goblin_fair.emissions import specie_of

SCENARIOS = ("with", "without")
METHODS = ("leave_one_out", "add")
# The adjusted world must not have negative global emissions of these.
_NON_NEGATIVE = ("CH4", "N2O")


@dataclass(frozen=True)
class RunOutput:
    years: np.ndarray
    members: np.ndarray
    with_: np.ndarray  # surface temperature, K, shape (n_years, n_members)
    without: np.ndarray


def fair_version() -> str:
    return fair.__version__


def run_pair(
    emissions: pd.DataFrame,
    background: str,
    end_year: int,
    members: None | int | Sequence[int] = None,
    method: str = "leave_one_out",
) -> RunOutput:
    """Run the SSP with and without `emissions` for the chosen ensemble members.

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

    # 2. leave_one_out takes the user's emissions out of "without";
    #    add puts them into "with". Year Y sits on FaIR timepoint Y + 0.5.
    scenario, sign = ("without", -1.0) if method == "leave_one_out" else ("with", 1.0)
    timepoints = emissions.index.to_numpy(dtype=float) + 0.5
    #    Stream labels ("CH4:biogenic") are bookkeeping: FaIR has one CH4, so
    #    every label of a gas is summed before it goes in.
    by_specie = emissions.T.groupby(specie_of, sort=False).sum().T
    for specie in by_specie.columns:
        selection = dict(specie=specie, scenario=scenario, timepoints=timepoints)
        adjusted = (
            f.emissions.loc[selection].to_numpy()
            + sign * by_specie[specie].to_numpy()[:, None]
        )
        if specie in _NON_NEGATIVE and (adjusted < 0).any():
            first = int(by_specie.index[(adjusted < 0).any(axis=1)][0])
            raise ValueError(
                f"{method} leaves negative global {specie} "
                f"emissions in {background} in {first}; check the units and "
                "that the emitter is part of the world total"
            )
        fill(f.emissions, adjusted, **selection)

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
        with_=surface.sel(scenario="with").to_numpy(),
        without=surface.sel(scenario="without").to_numpy(),
    )
