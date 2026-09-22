"""The maths behind solving for a neutral pathway (no FaIR runs)."""

import numpy as np
import pytest

from goblin_fair.pathway import decline_path, overshoot, solve_rate

YEARS = np.arange(2000, 2101)
FLAT = np.full(YEARS.size, 10.0)


def test_decline_path_keeps_the_past_and_cuts_from_the_pinned_year():
    path = decline_path(FLAT, YEARS, 2050, rate=0.02)
    np.testing.assert_allclose(path[YEARS < 2050], 10.0)
    np.testing.assert_allclose(path[YEARS == 2050], 9.8)  # the first year of action
    np.testing.assert_allclose(path[YEARS == 2060], 10.0 * 0.98**11)


def test_a_negative_rate_is_growth():
    path = decline_path(FLAT, YEARS, 2050, rate=-0.05)
    np.testing.assert_allclose(path[YEARS == 2050], 10.5)


def test_decline_path_needs_the_pinned_year_to_be_in_the_data():
    with pytest.raises(ValueError, match="from_year"):
        decline_path(FLAT, YEARS, 1990, rate=0.02)


def test_overshoot_measures_the_gap_above_the_pinned_level():
    warming = np.interp(YEARS, [2000, 2050, 2075, 2100], [0.0, 1.0, 1.4, 1.2])
    assert overshoot(warming, YEARS, 2050, 2100) == pytest.approx(0.2)
    assert overshoot(warming, YEARS, 2075, 2100) == pytest.approx(-0.2)


def test_overshoot_ignores_the_transition_years():
    # A bump before by_year does not count; what matters is where it ends up.
    warming = np.interp(YEARS, [2000, 2050, 2060, 2100], [0.0, 1.0, 2.0, 0.5])
    assert overshoot(warming, YEARS, 2050, 2060) == pytest.approx(1.0)
    assert overshoot(warming, YEARS, 2050, 2100) == pytest.approx(-0.5)


def test_overshoot_gives_one_number_per_ensemble_member():
    rising = np.interp(YEARS, [2000, 2050, 2100], [0.0, 1.0, 1.5])
    falling = np.interp(YEARS, [2000, 2050, 2100], [0.0, 1.0, 0.5])
    both = np.stack([rising, falling], axis=1)
    np.testing.assert_allclose(overshoot(both, YEARS, 2050, 2100), [0.5, -0.5])


def test_solve_rate_finds_the_smallest_cut_that_works():
    # Made-up model: every 1 % a year of cutting removes 0.2 K of overshoot,
    # starting from 0.5 K. The answer is therefore 2.5 % a year.
    calls = []

    def overshoot_at(rate):
        calls.append(rate)
        return 0.5 - 20.0 * rate

    rate, low, high = solve_rate(overshoot_at, steps=20)
    assert rate == pytest.approx(0.025, abs=1e-4)
    assert low <= 0.025 <= high
    assert len(calls) < 30, "the search should not need many runs"


def test_solve_rate_widens_the_range_when_a_bigger_cut_is_needed():
    rate, _, _ = solve_rate(lambda r: 1.0 - 4.0 * r, bounds=(0.0, 0.05), steps=20)
    assert rate == pytest.approx(0.25, abs=1e-3)


def test_solve_rate_allows_growth_when_the_entity_is_already_neutral():
    # Overshoot stays negative even while emissions grow.
    rate, _, _ = solve_rate(lambda r: -1.0 - r, bounds=(0.0, 0.05), steps=20)
    assert rate < 0


def test_solve_rate_stops_at_its_limit_when_nothing_works():
    rate, low, high = solve_rate(lambda r: 5.0, bounds=(0.0, 0.05), limits=(-0.2, 0.6))
    assert rate == 0.6
    assert low == high == rate, "a collapsed range says the search hit its limit"
