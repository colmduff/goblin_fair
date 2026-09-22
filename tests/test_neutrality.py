"""Warming rate and the year an entity stops adding warming (synthetic arrays)."""

import numpy as np
import pytest

from goblin_fair.results import ContributionResult

YEARS = np.arange(2000, 2101)


def result(curve, members=3):
    """A ContributionResult whose contribution follows `curve` for every member."""
    values = np.asarray(curve, dtype=float)[:, None].repeat(members, axis=1)
    zeros = np.zeros_like(values)
    return ContributionResult(YEARS, np.arange(members), values, zeros)


def test_warming_rate_of_a_straight_ramp_is_its_slope():
    rate = result(0.01 * (YEARS - 2000)).warming_rate(window=10)
    assert np.isnan(rate.loc[2000:2009].to_numpy()).all()  # no earlier year to compare
    np.testing.assert_allclose(rate.loc[2010:].to_numpy(), 0.01)


def test_warming_rate_window_of_one_is_the_year_on_year_change():
    rate = result(np.cumsum(np.ones(YEARS.size))).warming_rate(window=1)
    np.testing.assert_allclose(rate.loc[2001:].to_numpy(), 1.0)


@pytest.mark.parametrize("bad", [0, -1, 1.5, "10"])
def test_warming_rate_rejects_a_bad_window(bad):
    with pytest.raises(ValueError, match="window"):
        result(np.zeros(YEARS.size)).warming_rate(window=bad)


def test_peak_rule_finds_the_year_after_the_contribution_stops_rising():
    # Rises to 2050, falls after: the first year it is no longer rising is 2051.
    curve = -((YEARS - 2050) ** 2) / 1e4
    n = result(curve).neutrality(from_year=2025, rule="peak", window=1)
    assert list(n.years) == [2051, 2051, 2051]
    assert n.share_reached == 1.0
    assert n.by_share(0.5) == 2051


def test_hold_rule_finds_the_year_it_returns_to_the_pinned_level():
    # 1.0 in 2025, rises to 2050, back to 1.0 in 2075 and falling after.
    curve = np.interp(YEARS, [2000, 2025, 2050, 2075, 2100], [0.5, 1.0, 2.0, 1.0, 0.5])
    n = result(curve).neutrality(from_year=2025, rule="hold", window=1)
    assert list(n.years) == [2075, 2075, 2075]


def test_a_contribution_that_keeps_rising_never_reaches_neutrality():
    n = result(0.01 * (YEARS - 2000)).neutrality(from_year=2025, rule="peak", window=1)
    assert np.isnan(n.years).all()
    assert n.share_reached == 0.0
    assert n.by_share(0.5) is None


def test_tolerance_lets_a_slow_rise_count_as_neutral():
    curve = np.where(YEARS < 2050, 0.01 * (YEARS - 2000), 0.5 + 0.0001 * (YEARS - 2050))
    strict = result(curve).neutrality(from_year=2025, rule="peak", window=1)
    loose = result(curve).neutrality(
        from_year=2025, rule="peak", window=1, tolerance=0.0002
    )
    assert np.isnan(strict.years).all()
    assert list(loose.years) == [2051, 2051, 2051]  # 2050 still carries the old slope


def test_by_share_uses_every_member_including_those_that_never_reach_it():
    values = np.stack(
        [
            np.interp(YEARS, [2000, 2040, 2100], [0.0, 1.0, 0.0]),  # peaks 2040
            np.interp(YEARS, [2000, 2060, 2100], [0.0, 1.0, 0.0]),  # peaks 2060
            0.01 * (YEARS - 2000),  # never
        ],
        axis=1,
    )
    r = ContributionResult(YEARS, np.arange(3), values, np.zeros_like(values))
    n = r.neutrality(from_year=2025, rule="peak", window=1)
    assert n.share_reached == pytest.approx(2 / 3)
    assert n.by_share(0.5) == 2061
    assert n.by_share(0.9) is None  # only two of three ever get there


def test_neutrality_rejects_an_unknown_rule():
    with pytest.raises(ValueError, match="rule"):
        result(np.zeros(YEARS.size)).neutrality(from_year=2025, rule="flat")


def test_neutrality_rejects_a_from_year_outside_the_run():
    with pytest.raises(ValueError, match="from_year"):
        result(np.zeros(YEARS.size)).neutrality(from_year=1990)


def test_summary_table_reports_years_and_share():
    curve = -((YEARS - 2050) ** 2) / 1e4
    n = result(curve).neutrality(from_year=2025, rule="peak", window=1)
    s = n.summary()
    assert s["rule"] == "peak"
    assert s["from_year"] == 2025
    assert s["share_reached"] == 1.0
    assert s["p50"] == 2051
