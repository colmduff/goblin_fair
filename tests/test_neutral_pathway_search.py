"""The neutral-pathway search when growth is allowed (fast: a stand-in for FaIR)."""

import numpy as np
import pandas as pd
import pytest

import goblin_fair as gf
from goblin_fair import engine

YEARS = np.arange(1900, 2101)


def fake_engine(cap_mt):
    """Warming = emissions that fade over time; too much emission is an error.

    Stands in for engine.run_pair: the same inputs and outputs, no FaIR. Like
    the real engine, it refuses an emitter bigger than the world (`cap_mt`).
    """

    def run_pair(emissions, background, end_year, members=None, method=""):
        total = emissions.sum(axis=1)  # Mt CH4, every label of the gas summed
        if (total > cap_mt).any():
            first = int(total.index[(total > cap_mt).to_numpy()][0])
            raise ValueError(
                f"{method} leaves negative global CH4 emissions in {background} "
                f"in {first}; check the units"
            )
        years = np.arange(1750, end_year + 1)
        flow = np.zeros(years.size)
        flow[np.isin(years, total.index)] = total.to_numpy()
        warming = np.zeros(years.size)
        for i in range(1, years.size):  # year Y feels emissions before Y
            warming[i] = warming[i - 1] * np.exp(-1 / 8) + flow[i - 1] * 1e-3
        # Two "members" with different climates: methane's warming fades over
        # 8 years in one and 20 in the other, so they need different rates.
        slow = np.zeros(years.size)
        for i in range(1, years.size):
            slow[i] = slow[i - 1] * np.exp(-1 / 20) + flow[i - 1] * 1e-3
        both = np.column_stack([warming, slow])
        return engine.RunOutput(years, np.array([0, 1]), both, np.zeros_like(both))

    return run_pair


def fading_fossil():
    """Steady biogenic methane; fossil methane high in the past, gone after 2020."""
    fossil = np.where(
        YEARS < 2020, 3000.0, np.maximum(0.0, 3000.0 - 300 * (YEARS - 2019))
    )
    return pd.DataFrame(
        {"CH4:biogenic": 1000.0, "CH4:fossil": fossil}, index=YEARS
    )  # kt


def test_growth_is_found_even_when_the_search_overshoots_the_world(monkeypatch):
    # With fossil methane fading, biogenic methane may grow. The search tries
    # fast growth first; that would make this emitter bigger than the world,
    # which counts as "too much warming", not as a crash.
    monkeypatch.setattr(engine, "run_pair", fake_engine(cap_mt=20.0))
    out = gf.neutral_pathway(
        fading_fossil(), solve="CH4:biogenic", from_year=2020, by_year=2050,
        units="kt", end_year=2101,
    )  # fmt: skip
    assert out.decline["p50"] < 0, "growth is allowed"
    assert np.isfinite(list(out.decline.values())).all()
    assert out.verification["share_neutral"] > 0
    assert out.emissions["CH4:biogenic"].max() <= 20_000.0


def test_an_emitter_bigger_than_the_world_without_growth_is_still_an_error(
    monkeypatch,
):
    # If even the history is bigger than the world, the problem is the input
    # (usually units), so the error must reach the user.
    monkeypatch.setattr(engine, "run_pair", fake_engine(cap_mt=2.0))
    with pytest.raises(ValueError, match="negative global CH4"):
        gf.neutral_pathway(
            fading_fossil(), solve="CH4:biogenic", from_year=2020, by_year=2050,
            units="kt", end_year=2101,
        )  # fmt: skip


def test_the_member_range_is_measured_on_both_sides_of_the_answer(monkeypatch):
    # When 0 % already works for the median, the search only tries growth. A
    # member that needs a cut must still get a real rate, not be clipped at 0.
    monkeypatch.setattr(engine, "run_pair", fake_engine(cap_mt=20.0))
    out = gf.neutral_pathway(
        fading_fossil(), solve="CH4:biogenic", from_year=2020, by_year=2050,
        units="kt", end_year=2101,
    )  # fmt: skip
    rates = out.member_declines.to_numpy()
    assert rates[0] != pytest.approx(rates[1]), "the two climates differ"
    tried = sorted(out.verification["rates_tried"])
    for rate in rates:  # both in % a year
        assert tried[0] <= rate <= tried[-1]
        assert rate not in (tried[0], tried[-1]), "each member is bracketed"


def test_a_member_next_to_an_impossible_rate_gets_the_rate_known_to_work():
    # Rates run from growth (negative) to cuts. Both members fail at -10 %
    # (bigger than the world: infinite overshoot) and pass at 0 %, so each
    # one's rate is 0 %: the gentlest rate known to work, never NaN.
    from goblin_fair.api import _member_rates

    tried = {
        -0.10: np.array([np.inf, np.inf]),
        0.0: np.array([-1.0, -0.5]),
        0.05: np.array([-3.0, -2.0]),
    }
    np.testing.assert_array_equal(_member_rates(tried), [0.0, 0.0])
