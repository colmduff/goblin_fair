import numpy as np
import pandas as pd
import pytest

from goblin_fair.emissions import prepare_emissions


def frame(**cols):
    return pd.DataFrame(cols, index=pd.Index([2020, 2021], name="year"))


def test_kilotonnes_convert_to_fair_units():
    out = prepare_emissions(
        frame(CO2=[1000.0, 2000.0], CH4=[1000.0, 0.0], N2O=[1000.0, 0.0])
    )
    assert list(out.columns) == ["CO2 FFI", "CH4", "N2O"]
    np.testing.assert_allclose(out["CO2 FFI"], [1e-3, 2e-3])  # Gt CO2
    np.testing.assert_allclose(out["CH4"], [1.0, 0.0])  # Mt CH4
    np.testing.assert_allclose(out["N2O"], [1.0, 0.0])  # Mt N2O


@pytest.mark.parametrize(
    "unit,factor", [("t", 1e-9), ("kt", 1e-6), ("Mt", 1e-3), ("Gt", 1.0)]
)
def test_co2_prefixes(unit, factor):
    out = prepare_emissions(frame(CO2=[1.0, 1.0]), units=unit)
    np.testing.assert_allclose(out["CO2 FFI"], factor)


def test_units_per_column_and_case_insensitive_names():
    out = prepare_emissions(
        frame(co2_ffi=[1.0, 1.0], Co2_Afolu=[1.0, 1.0], ch4=[1.0, 1.0]),
        units={"CO2_FFI": "Gt", "co2_afolu": "Mt", "CH4": "kt"},
    )
    assert list(out.columns) == ["CO2 FFI", "CO2 AFOLU", "CH4"]
    np.testing.assert_allclose(out["CO2 FFI"], 1.0)
    np.testing.assert_allclose(out["CO2 AFOLU"], 1e-3)
    np.testing.assert_allclose(out["CH4"], 1e-3)


def test_output_columns_follow_fair_order_not_input_order():
    out = prepare_emissions(frame(N2O=[1.0, 1.0], CO2=[1.0, 1.0]))
    assert list(out.columns) == ["CO2 FFI", "N2O"]


def test_negative_values_allowed():
    out = prepare_emissions(frame(CO2=[-5.0, 1.0]), units="Gt")
    assert out["CO2 FFI"].iloc[0] == -5.0


def test_integer_like_index_accepted_and_output_index_is_int():
    df = pd.DataFrame({"CH4": [1.0]}, index=[2030.0])
    out = prepare_emissions(df)
    assert out.index.tolist() == [2030]
    assert out.index.name == "year"


def test_input_is_not_modified():
    df = frame(co2=[1.0, 2.0])
    before = df.copy()
    prepare_emissions(df)
    pd.testing.assert_frame_equal(df, before)


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
        (frame(CO2=[True, False]), "kt", "numeric"),
        (frame(CO2=[1.0, 1.0]), "mt", "units"),
        (frame(CO2=[1.0, 1.0]), {"CH4": "kt"}, "CO2"),
        (frame(co2=[1.0, 1.0], CO2=[1.0, 1.0]), "kt", "duplicate"),
        (pd.DataFrame(), "kt", "at least one"),
    ],
)
def test_invalid_inputs_raise(df, units, match):
    with pytest.raises(ValueError, match=match):
        prepare_emissions(df, units=units)


def test_non_dataframe_raises():
    with pytest.raises(ValueError, match="DataFrame"):
        prepare_emissions({"CO2": [1.0]})


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


def test_non_numeric_index_raises():
    df = pd.DataFrame({"CH4": [1.0, 1.0]}, index=["a", "b"])
    with pytest.raises(ValueError, match="years"):
        prepare_emissions(df)


def test_gap_in_years_warns():
    df = pd.DataFrame({"CH4": [1.0, 1.0]}, index=[2020, 2025])
    with pytest.warns(UserWarning, match="zero"):
        prepare_emissions(df)
