"""Real FaIR runs with a few ensemble members (marked slow)."""

import numpy as np
import pandas as pd
import pytest

import goblin_fair as gf
from tests.conftest import N_MEMBERS

pytestmark = pytest.mark.slow


def test_zero_emissions_give_zero_contribution():
    # Also proves the calibrated stochastic variability is identical in both
    # scenarios and cancels in the difference.
    df = pd.DataFrame({"CO2": 0.0, "CH4": 0.0, "N2O": 0.0}, index=range(2020, 2050))
    res = gf.temperature_contribution(df, end_year=2060, members=N_MEMBERS)
    np.testing.assert_allclose(res.ensemble.to_numpy(), 0.0, atol=1e-12)


def test_co2_pulse_no_effect_before_and_warming_after(co2_pulse_result):
    ens = co2_pulse_result.ensemble
    assert ens.shape == (2080 - 1750 + 1, N_MEMBERS)
    np.testing.assert_allclose(ens.loc[:2030].to_numpy(), 0.0, atol=1e-12)
    assert (ens.loc[2031:] > 0).all().all()


def test_contribution_scales_nearly_linearly(co2_pulse_result):
    df = pd.DataFrame({"CO2": 20.0}, index=range(2030, 2040))
    double = gf.temperature_contribution(
        df, units="Gt", end_year=2080, members=N_MEMBERS
    )
    ratio = double.ensemble.loc[2080] / co2_pulse_result.ensemble.loc[2080]
    assert ((ratio > 1.9) & (ratio < 2.1)).all()


def test_methane_response_decays_faster_than_co2(co2_pulse_result):
    df = pd.DataFrame({"CH4": 300.0}, index=range(2030, 2040))
    ch4 = gf.temperature_contribution(
        df, units="Mt", end_year=2080, members=N_MEMBERS
    ).summary()["p50"]
    co2 = co2_pulse_result.summary()["p50"]
    assert ch4.loc[2080] / ch4.max() < co2.loc[2080] / co2.max()


def test_units_are_applied_before_running(co2_pulse_result):
    df = pd.DataFrame({"CO2": 10_000.0}, index=range(2030, 2040))
    same = gf.temperature_contribution(df, units="Mt", end_year=2080, members=N_MEMBERS)
    np.testing.assert_allclose(same.ensemble, co2_pulse_result.ensemble, rtol=1e-9)


def test_result_metadata_and_background(co2_pulse_result):
    md = co2_pulse_result.metadata
    assert md["fair_version"] == "2.2.4"
    assert md["calibration"] == "1.4.1"
    assert md["background"] == "ssp245"
    assert md["background_source"] == "RCMIP v5.1.0"
    assert md["n_members"] == N_MEMBERS
    assert md["species"] == {"CO2 FFI": "Gt CO2/yr"}
    bw = co2_pulse_result.background_warming()
    assert 0.8 < bw.loc[2020, "p50"] < 1.6


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
        species, props = read_properties(
            filename=str(_data.data_path(_data.SPECIES_FILE))
        )
        f.define_species(species, props)
        f.allocate()
        return f

    ours, theirs = allocated(), allocated()
    ours.fill_from_pandas("emissions", _data.load_background("ssp245"))
    theirs.fill_from_rcmip()
    np.testing.assert_allclose(
        ours.emissions.to_numpy(), theirs.emissions.to_numpy(), rtol=1e-9, atol=0
    )
