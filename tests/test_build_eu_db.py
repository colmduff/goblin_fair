"""The EU27 net-zero database builder (scripts/build_eu_db.py), on made-up data."""

import importlib.util
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_eu_db.py"
_spec = importlib.util.spec_from_file_location("build_eu_db", _PATH)
eu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eu)

YEARS = [2005, 2010, 2020, 2030]


def iamc(rows):
    """A tiny wide IAMC table: (scenario, variable, unit, values by YEARS)."""
    records = [
        {"Model": "M", "Scenario": s, "Region": "EU27", "Variable": v, "Unit": u}
        | dict(zip(YEARS, values, strict=True))
        for s, v, u, values in rows
    ]
    return pd.DataFrame(records)


def complete(scenario="NZero_withICEPhOP", **override):
    base = {
        "Emissions|CO2": ("Mt CO2/yr", [100.0, 80.0, 60.0, 20.0]),
        "Emissions|CO2|AFOLU": ("Mt CO2/yr", [-10.0, -10.0, -12.0, -14.0]),
        "Emissions|CH4": ("Mt CH4/yr", [16.0, 15.0, 13.0, 9.0]),
        "Emissions|N2O": ("kt N2O/yr", [860.0, 730.0, 850.0, 670.0]),
    }
    base.update(override)
    return [(scenario, v, u, vals) for v, (u, vals) in base.items()]


def test_fair_input_is_annual_in_kt_and_keeps_reported_years_exactly():
    out = eu.to_fair_input(iamc(complete()))
    assert list(out.columns) == [
        "scenario",
        "year",
        "CO2_FFI",
        "CO2_AFOLU",
        "CH4",
        "N2O",
    ]
    one = out.set_index("year")
    assert list(one.index) == list(range(2005, 2031))
    assert one.loc[2020, "CH4"] == 13_000.0  # Mt -> kt
    assert one.loc[2020, "N2O"] == 850.0  # already kt
    assert one.loc[2020, "CO2_AFOLU"] == -12_000.0
    # halfway between 2010 (15 Mt) and 2020 (13 Mt)
    assert one.loc[2015, "CH4"] == pytest.approx(14_000.0)


def test_co2_ffi_is_the_co2_total_minus_afolu():
    out = eu.to_fair_input(iamc(complete())).set_index("year")
    np.testing.assert_allclose(
        (out["CO2_FFI"] + out["CO2_AFOLU"]).loc[YEARS], [100e3, 80e3, 60e3, 20e3]
    )


def test_each_scenario_gets_its_own_rows():
    table = iamc(complete("A") + complete("B"))
    out = eu.to_fair_input(table)
    assert sorted(out["scenario"].unique()) == ["A", "B"]
    assert len(out) == 2 * 26


def test_a_missing_total_is_an_error_not_a_zero():
    rows = [r for r in complete() if r[1] != "Emissions|N2O"]
    with pytest.raises(ValueError, match="Emissions\\|N2O"):
        eu.to_fair_input(iamc(rows))


def test_an_unexpected_unit_is_an_error():
    with pytest.raises(ValueError, match="unit"):
        eu.to_fair_input(iamc(complete(**{"Emissions|CH4": ("Gg CH4/yr", [1.0] * 4)})))


def test_the_three_net_zero_scenarios_are_picked_by_name():
    assert eu.NZ_SCENARIOS == (
        "NZero_withICEPhOP",
        "NZero_bioLim12_withICEPhOP",
        "NZero_bioLim7p5_withICEPhOP",
    )
    table = iamc(complete("NZero_withICEPhOP") + complete("def_300_withICEPhOP"))
    kept = eu.keep_scenarios(table, eu.NZ_SCENARIOS)
    assert list(kept["Scenario"].unique()) == ["NZero_withICEPhOP"]


def test_scenarios_come_out_in_the_order_asked_for():
    table = iamc(complete("NZero_bioLim12_withICEPhOP") + complete("NZero_withICEPhOP"))
    kept = eu.keep_scenarios(table, eu.NZ_SCENARIOS)
    assert list(kept["Scenario"].unique()) == [
        "NZero_withICEPhOP",
        "NZero_bioLim12_withICEPhOP",
    ]
    # so the reference case is the one others are "identical to"
    assert eu.identical_to(kept)["NZero_bioLim12_withICEPhOP"] == "NZero_withICEPhOP"


def test_catalogue_says_what_each_variable_feeds():
    names = [
        "Emissions|CO2",
        "Emissions|CO2|AFOLU",
        "Emissions|CO2|Energy|Supply",
        "Emissions|CO2|Energy|Demand|Bunkers",
        "Emissions|CH4",
        "Emissions|CH4|Waste",
        "Emissions|F-Gases",
        "Carbon Removal|Land Use",
        "Final Energy|Industry",
    ]
    table = iamc([("S", v, "u", [1.0] * 4) for v in names])
    cat = eu.catalogue(table).set_index("variable")
    assert cat.loc["Emissions|CH4", "fair_input"] == "CH4"
    assert cat.loc["Emissions|CO2|AFOLU", "fair_input"] == "CO2_AFOLU"
    assert cat.loc["Emissions|CO2", "fair_input"] == "CO2_FFI + CO2_AFOLU"
    assert cat.loc["Emissions|CH4|Waste", "part_of"] == "CH4"
    assert cat.loc["Emissions|CO2|Energy|Supply", "part_of"] == "CO2_FFI"
    assert cat.loc["Emissions|CO2|Energy|Demand|Bunkers", "part_of"] == ""
    assert "bunkers" in cat.loc["Emissions|CO2|Energy|Demand|Bunkers", "note"].lower()
    for unused in [
        "Emissions|F-Gases",
        "Carbon Removal|Land Use",
        "Final Energy|Industry",
    ]:
        assert cat.loc[unused, "fair_input"] == ""
        assert cat.loc[unused, "part_of"] == ""
        assert cat.loc[unused, "note"]
    assert cat.loc["Final Energy|Industry", "group"] == "Final Energy"


def test_breakdown_gaps_measure_what_the_parts_miss():
    rows = complete() + [
        ("NZero_withICEPhOP", f"Emissions|CH4|{p}", "Mt CH4/yr", vals)
        for p, vals in [
            ("AFOLU|Agriculture", [8.0, 8.0, 8.0, 7.0]),
            ("Waste", [5.0, 4.0, 3.0, 2.0]),
        ]
    ]
    gaps = eu.breakdown_gaps(iamc(rows))
    ch4 = gaps[gaps["gas"] == "CH4"].set_index("year")
    assert ch4.loc[2005, "gap"] == pytest.approx(3.0)  # 16 - (8 + 5)
    assert ch4.loc[2030, "gap"] == pytest.approx(0.0)
    assert ch4.loc[2005, "gap_pct"] == pytest.approx(100 * 3 / 16)


def test_identical_scenarios_are_detected():
    table = iamc(complete("A") + complete("B") + complete("C", **{
        "Emissions|CH4": ("Mt CH4/yr", [16.0, 15.0, 13.0, 8.0])
    }))  # fmt: skip
    assert eu.identical_to(table) == {"A": "", "B": "A", "C": ""}


def test_write_db_creates_the_tables(tmp_path):
    path = tmp_path / "x.sqlite"
    eu.write_db(path, {"fair_input": eu.to_fair_input(iamc(complete()))})
    with sqlite3.connect(path) as con:
        n = con.execute("select count(*) from fair_input").fetchone()[0]
    assert n == 26


# --- methane history (PRIMAP-hist) and biogenic / fossil streams -------------

PRIMAP_YEARS = ["1750", "1900", "2004", "2005"]


def primap(values_by_category, area="EU27BX", scenario="HISTCR"):
    """A tiny PRIMAP-hist table: category -> values for PRIMAP_YEARS, Gg CH4/yr."""
    return pd.DataFrame(
        [
            {
                "source": "PRIMAP-hist_v2.6.1_final",
                "scenario (PRIMAP-hist)": scenario,
                "provenance": "derived",
                "area (ISO3)": area,
                "entity": "CH4",
                "unit": "CH4 * gigagram / yr",
                "category (IPCC2006_PRIMAP)": cat,
            }
            | dict(zip(PRIMAP_YEARS, vals, strict=True))
            for cat, vals in values_by_category.items()
        ]
    )


EU_CH4 = {
    "M.AG": [3000.0, 7000.0, 9000.0, 9000.0],
    "4": [200.0, 500.0, 5000.0, 5000.0],
    "1": [1500.0, 4800.0, 4000.0, 4000.0],
    "2": [0.0, 10.0, 80.0, 80.0],
    "5": [0.0, 0.0, 0.0, 0.0],
    "M.0.EL": [4700.0, 12310.0, 18080.0, 18080.0],
}


def test_primap_streams_are_agriculture_plus_waste_and_the_rest_in_kt():
    table = pd.concat([primap(EU_CH4), primap(EU_CH4, area="DEU")])
    out = eu.primap_ch4_streams(table)
    assert list(out.columns) == ["biogenic", "fossil"]
    assert list(out.index) == [1750, 1900, 2004, 2005]
    assert out.loc[1900, "biogenic"] == 7500.0  # Gg = kt
    assert out.loc[1900, "fossil"] == 4810.0


def test_primap_streams_must_add_up_to_the_national_total():
    bad = dict(EU_CH4, **{"M.0.EL": [9999.0, 12310.0, 18080.0, 18080.0]})
    with pytest.raises(ValueError, match="M.0.EL"):
        eu.primap_ch4_streams(primap(bad))


def test_primap_missing_category_is_an_error():
    missing = {k: v for k, v in EU_CH4.items() if k != "4"}
    with pytest.raises(ValueError, match="'4'"):
        eu.primap_ch4_streams(primap(missing))


def ch4_parts(scenario="NZero_withICEPhOP"):
    parts = {
        "Emissions|CH4": [16.0, 15.0, 13.0, 9.0],
        "Emissions|CH4|AFOLU|Agriculture": [8.0, 8.0, 8.0, 7.0],
        "Emissions|CH4|AFOLU|Land": [0.0, 0.0, 0.0, 0.0],
        "Emissions|CH4|Waste": [5.0, 4.0, 3.0, 2.0],
    }
    return [(scenario, v, "Mt CH4/yr", vals) for v, vals in parts.items()]


def test_esabcc_streams_split_the_total_so_nothing_is_lost():
    out = eu.esabcc_ch4_streams(iamc(ch4_parts()))
    one = out.set_index("year")
    assert list(one.index) == list(range(2005, 2031))
    assert one.loc[2005, "biogenic"] == 13_000.0
    assert one.loc[2005, "fossil"] == 3_000.0  # total minus biogenic, kt
    np.testing.assert_allclose(one["biogenic"] + one["fossil"], one["total"])


def test_join_scales_history_to_meet_the_projection():
    history = pd.DataFrame(
        {"biogenic": [100.0, 200.0, 260.0], "fossil": [10.0, 40.0, 50.0]},
        index=pd.Index([2003, 2004, 2005], name="year"),
    )
    projection = pd.DataFrame(
        {"biogenic": [130.0, 120.0], "fossil": [40.0, 30.0]},
        index=pd.Index([2005, 2006], name="year"),
    )
    joined, factors = eu.join_history(history, projection, year=2005)
    f = factors.set_index("stream")["factor"]
    assert f["biogenic"] == pytest.approx(0.5)
    assert f["fossil"] == pytest.approx(0.8)
    assert list(joined.index) == [2003, 2004, 2005, 2006]
    assert joined.loc[2004, "biogenic"] == pytest.approx(100.0)  # 200 x 0.5
    assert joined.loc[2005, "biogenic"] == 130.0  # the projection itself
    assert list(joined["source"]) == ["PRIMAP-hist", "PRIMAP-hist", "ESABCC", "ESABCC"]
    np.testing.assert_allclose(joined["total"], joined["biogenic"] + joined["fossil"])


def test_join_needs_the_join_year_in_both():
    history = pd.DataFrame({"biogenic": [1.0], "fossil": [1.0]}, index=[2004])
    projection = pd.DataFrame({"biogenic": [1.0], "fossil": [1.0]}, index=[2005])
    with pytest.raises(ValueError, match="2005"):
        eu.join_history(history, projection, year=2005)


# --- Ireland: PRIMAP-hist without category 5, the Irish workbook, the 2020 join ---


def test_a_missing_other_category_counts_as_zero():
    no_other = {k: v for k, v in EU_CH4.items() if k != "5"}
    out = eu.primap_ch4_streams(primap(no_other, area="IRL"), area="IRL")
    assert out.loc[1900, "fossil"] == 4810.0  # 1 + 2, no 5


def test_primap_series_gives_the_national_total_in_kt():
    table = primap(EU_CH4)
    table["entity"] = "N2O"
    table["unit"] = "N2O * gigagram / yr"
    out = eu.primap_series(table, area="EU27BX", entity="N2O")
    assert out.loc[1900] == 12310.0


IRISH_HEADER = (
    "model",
    "region",
    "scenario",
    "unit",
    "variable",
    "2020-01-01",
    "2021-01-01",
    "2022-01-01",
)
MAGICC_ROW = ("MAGICCv7.5.3", "delta", "World", "TN", "kelvin")


def test_irish_emissions_are_read_into_fair_columns():
    series = [
        (
            "kt CO2/yr",
            "Emissions|CO2|MAGICC Fossil and Industrial",
            (100.0, 90.0, 80.0),
        ),
        ("kt CO2/yr", "Emissions|CO2|MAGICC AFOLU", (5.0, 4.0, 3.0)),
        ("kt CH4/yr", "Emissions|CH4", (650.0, 640.0, 630.0)),
        ("kt N2O/yr", "Emissions|N2O", (27.0, 26.0, 25.0)),
    ]
    rows = [IRISH_HEADER] + [("CPD", "World", "TN", u, v, *x) for u, v, x in series]
    out = eu.parse_irish_emissions(rows).set_index("year")
    assert list(out.columns) == ["scenario", "CO2_FFI", "CO2_AFOLU", "CH4", "N2O"]
    assert list(out.index) == [2020, 2021, 2022]
    assert out.loc[2021, "CH4"] == 640.0


def test_irish_magicc_contributions_are_read_by_gas_in_mk():
    header = ("baseline", "climate_model", "model", "region", "scenario", "unit")
    header += ("variable", "1/01/2020 0:00", "1/01/2021 0:00", None)  # empty columns
    rows = [
        header,
        ("Total Warming",) + (None,) * 9,
        ("ssp126", *MAGICC_ROW, "Surface Air Temperature Change", 0.003, 0.004, None),
        ("Methane",) + (None,) * 9,
        ("TN", *MAGICC_ROW, "Methane Contribution", 0.0009, 0.001, None),
        ("Year", "NZ-IE-CH4") + (None,) * 7,  # a second table starts: stop
        (2020, 0.1) + (None,) * 7,
    ]  # fmt: skip
    out = eu.parse_irish_magicc(rows)
    assert set(out["gas"]) == {"total", "CH4"}
    ch4 = out[out["gas"] == "CH4"].set_index("year")["warming_mK"]
    assert ch4.loc[2020] == pytest.approx(0.9)
    assert set(out["background"]) == {"ssp126"}


def test_irish_history_is_joined_at_2020_per_gas():
    scenario = pd.DataFrame(
        {"scenario": "TN", "year": [2020, 2021], "CO2_FFI": [200.0, 190.0],
         "CO2_AFOLU": [5.0, 4.0], "CH4": [650.0, 640.0], "N2O": [27.0, 26.0]}
    )  # fmt: skip
    history = pd.DataFrame(
        {"CO2_FFI": [50.0, 100.0], "CH4": [300.0, 616.0], "N2O": [10.0, 30.0]},
        index=pd.Index([2019, 2020], name="year"),
    )
    joined, factors = eu.join_irish(scenario, history, year=2020)
    f = factors.set_index("gas")["factor"]
    assert f["CH4"] == pytest.approx(650 / 616)
    one = joined.set_index("year")
    assert one.loc[2019, "CH4"] == pytest.approx(300 * 650 / 616)
    assert one.loc[2019, "CO2_AFOLU"] == 0.0  # no history in PRIMAP-hist main file
    assert one.loc[2020, "CH4"] == 650.0
    assert list(one["source"]) == ["PRIMAP-hist", "Irish workbook", "Irish workbook"]
