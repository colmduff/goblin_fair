"""Solving for the cut that keeps an entity's warming flat (real FaIR runs)."""

import numpy as np
import pandas as pd
import pytest

import goblin_fair as gf
from goblin_fair.pathway import overshoot

pytestmark = pytest.mark.slow

MEMBERS = 8
YEARS = list(range(1970, 2100))


def steady_methane(kt=500.0, column="CH4"):
    """An entity emitting the same amount of methane every year."""
    return pd.DataFrame({column: kt}, index=YEARS)


def run(emissions):
    return gf.temperature_contribution(
        emissions, units="kt", end_year=2100, members=MEMBERS
    )


@pytest.fixture(scope="module")
def solved():
    return gf.neutral_pathway(
        steady_methane(),
        solve="CH4",
        from_year=2025,
        units="kt",
        end_year=2100,
        members=MEMBERS,
    )


def test_a_steady_emitter_has_to_cut_slowly_not_stop(solved):
    assert 0 < solved.decline["p50"] < 5, "a few % a year at most, not a collapse"
    path = solved.pathway["p50"]
    assert path.loc[2099] < path.loc[2050] < path.loc[2025] <= 500.0
    assert path.loc[2099] > 200.0


def test_the_answer_really_does_hold_warming_flat(solved):
    # The proof: put the solved emissions through the ordinary public API.
    ensemble = run(solved.emissions).ensemble
    still_above = overshoot(ensemble.to_numpy(), ensemble.index.to_numpy(), 2025, 2099)
    pinned = np.median(ensemble.loc[2025].to_numpy())
    assert np.median(still_above) <= 0.01 * pinned
    assert (still_above <= 0).mean() >= 0.4


def test_it_reports_the_share_of_members_it_worked_for(solved):
    v = solved.verification
    assert 0.3 <= v["share_neutral"] <= 0.7, "the median member sits on the line"
    assert abs(v["overshoot_K"]) < 0.02 * v["pinned_K"]
    assert v["runs"] >= 5


def test_a_gentler_cut_would_not_be_enough(solved):
    # The reported rate is the smallest that works, so backing off must fail.
    gentler = solved.emissions.copy()
    rate = solved.decline["p50"] / 100 - 0.002
    years = np.array(YEARS)
    gentler["CH4"] = np.where(
        years >= 2025, 500.0 * (1 - rate) ** (years - 2025 + 1), 500.0
    )
    ensemble = run(gentler).ensemble
    still_above = overshoot(ensemble.to_numpy(), ensemble.index.to_numpy(), 2025, 2099)
    assert np.median(still_above) > 0


def test_members_disagree_about_how_fast_to_cut(solved):
    spread = solved.decline["p95"] - solved.decline["p5"]
    assert spread > 0.05, "different climates need different cuts"
    assert solved.decline["p5"] < solved.decline["p50"] < solved.decline["p95"]


def test_allowance_is_the_gap_from_the_pathway_you_gave(solved):
    gap = solved.allowance["p50"]
    assert (gap.loc[2030:2099] < 0).all(), "a steady emitter has to cut"
    np.testing.assert_allclose(
        solved.pathway["p50"].loc[2030] - 500.0, gap.loc[2030], rtol=1e-9
    )
    assert solved.cumulative_allowance()["p50"] < 0


def test_an_entity_already_cutting_fast_is_allowed_to_emit_more():
    steep = [500.0] * 55 + [500.0 * 0.97**i for i in range(75)]
    out = gf.neutral_pathway(
        pd.DataFrame({"CH4": steep}, index=YEARS),
        solve="CH4",
        from_year=2025,
        units="kt",
        end_year=2100,
        members=MEMBERS,
    )
    assert out.decline["p50"] < 3.0, "it can cut more slowly than 3 % a year"
    assert (out.allowance["p50"].loc[2050:2099] > 0).all()


def test_solving_one_stream_leaves_the_others_alone():
    df = pd.DataFrame(
        {"CH4:biogenic": 400.0, "CH4:fossil": 100.0, "N2O": 20.0}, index=YEARS
    )
    out = gf.neutral_pathway(
        df,
        solve="CH4:biogenic",
        from_year=2025,
        units="kt",
        end_year=2100,
        members=MEMBERS,
    )
    pd.testing.assert_series_equal(out.emissions["CH4:fossil"], df["CH4:fossil"])
    pd.testing.assert_series_equal(out.emissions["N2O"], df["N2O"])
    assert out.emissions["CH4:biogenic"].loc[2050] < 400.0


def test_an_earlier_target_year_demands_a_faster_cut():
    common = dict(
        solve="CH4", from_year=2025, units="kt", end_year=2100, members=MEMBERS
    )
    soon = gf.neutral_pathway(steady_methane(), by_year=2050, **common)
    later = gf.neutral_pathway(steady_methane(), by_year=2090, **common)
    assert soon.decline["p50"] > later.decline["p50"]


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"solve": "CO2"}, "solve"),
        ({"from_year": 2150}, "from_year"),
        ({"by_year": 2020}, "by_year"),
        ({"by_year": 2200}, "by_year"),
    ],
)
def test_invalid_arguments_are_rejected(kwargs, match):
    call = dict(solve="CH4", from_year=2025, units="kt", members=MEMBERS)
    call.update(kwargs)
    with pytest.raises(ValueError, match=match):
        gf.neutral_pathway(steady_methane(), **call)
