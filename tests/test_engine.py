"""Real FaIR runs with a few ensemble members (marked slow)."""

import numpy as np
import pandas as pd
import pytest

import goblin_fair as gf
from tests.conftest import N_MEMBERS

pytestmark = pytest.mark.slow


@pytest.mark.parametrize("method", ["leave_one_out", "add"])
def test_zero_emissions_give_zero_contribution(method):
    # Also proves the calibrated stochastic variability is identical in both
    # scenarios and cancels in the difference.
    df = pd.DataFrame({"CO2": 0.0, "CH4": 0.0, "N2O": 0.0}, index=range(2020, 2050))
    res = gf.temperature_contribution(
        df, end_year=2060, members=N_MEMBERS, method=method
    )
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
    assert md["method"] == "leave_one_out"
    assert md["n_members"] == N_MEMBERS
    assert md["species"] == {"CO2 FFI": "Gt CO2/yr"}
    assert (md["first_emission_year"], md["last_emission_year"]) == (2030, 2039)
    bw = co2_pulse_result.background_warming()
    assert 0.8 < bw.loc[2020, "p50"] < 1.6


def test_background_warming_is_the_same_ssp_run_for_both_methods(co2_pulse_result):
    df = pd.DataFrame({"CO2": 10.0}, index=range(2030, 2040))
    added = gf.temperature_contribution(
        df, units="Gt", end_year=2080, members=N_MEMBERS, method="add"
    )
    pd.testing.assert_frame_equal(
        added.background_warming(), co2_pulse_result.background_warming()
    )


def test_leave_one_out_close_to_add_for_a_small_region():
    df = pd.DataFrame({"CO2": 50.0, "CH4": 0.5, "N2O": 0.03}, index=range(1990, 2030))
    kwargs = dict(units="Mt", end_year=2060, members=N_MEMBERS)
    loo = gf.temperature_contribution(df, method="leave_one_out", **kwargs)
    add = gf.temperature_contribution(df, method="add", **kwargs)
    np.testing.assert_allclose(
        loo.ensemble.loc[2060], add.ensemble.loc[2060], rtol=0.02
    )


def test_leave_one_out_rejects_removing_more_methane_than_the_world_emits():
    df = pd.DataFrame({"CH4": 10_000.0}, index=range(2020, 2025))
    with pytest.raises(ValueError, match="CH4"):
        gf.temperature_contribution(df, units="Mt", end_year=2040, members=2)


@pytest.mark.parametrize("column", ["CO2_AFOLU", "N2O"])
def test_afolu_co2_and_n2o_alone_warm(column):
    df = pd.DataFrame({column: 1.0}, index=range(2000, 2030))
    res = gf.temperature_contribution(df, units="Mt", end_year=2050, members=N_MEMBERS)
    assert (res.ensemble.loc[2031:] > 0).all().all()


def test_explicit_member_list_runs_in_the_given_order():
    from goblin_fair import _data

    ids = list(_data.load_parameters().index[[4, 1]])
    df = pd.DataFrame({"CH4": 1.0}, index=range(2020, 2030))
    res = gf.temperature_contribution(df, units="Mt", end_year=2040, members=ids)
    assert list(res.members) == ids
    assert list(res.ensemble.columns) == ids


def test_two_streams_of_one_gas_equal_one_combined_column():
    # A label is bookkeeping: FaIR sees one CH4, so the split must not change
    # the answer at all.
    split = pd.DataFrame(
        {"CH4:biogenic": 300.0, "CH4:fossil": 200.0}, index=range(2000, 2030)
    )
    whole = pd.DataFrame({"CH4": 500.0}, index=range(2000, 2030))
    kwargs = dict(units="kt", end_year=2050, members=N_MEMBERS)
    a = gf.temperature_contribution(split, **kwargs)
    b = gf.temperature_contribution(whole, **kwargs)
    np.testing.assert_allclose(a.ensemble.to_numpy(), b.ensemble.to_numpy(), rtol=1e-12)
    assert a.metadata["streams"] == ["CH4:biogenic", "CH4:fossil"]
    assert a.metadata["species"] == {
        "CH4:biogenic": "Mt CH4/yr",
        "CH4:fossil": "Mt CH4/yr",
    }


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
