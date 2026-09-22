import matplotlib

matplotlib.use("Agg")

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from goblin_fair.results import ContributionResult  # noqa: E402


@pytest.fixture
def result():
    years = np.arange(1750, 2101)
    members = np.array([10, 20, 30, 40, 50])
    rng = np.random.default_rng(0)
    background = rng.normal(size=(years.size, members.size))
    contribution = np.outer(np.linspace(0, 1, years.size), [1.0, 2.0, 3.0, 4.0, 5.0])
    return ContributionResult(
        years,
        members,
        with_temperature=background + contribution,
        without_temperature=background,
        metadata={"background": "ssp245"},
    )


def test_ensemble_is_member_wise_difference(result):
    ens = result.ensemble
    assert ens.shape == (351, 5)
    assert list(ens.columns) == [10, 20, 30, 40, 50]
    assert ens.index.name == "year"
    np.testing.assert_allclose(ens.loc[2100].to_numpy(), [1, 2, 3, 4, 5])


def test_summary_default_quantiles(result):
    s = result.summary()
    assert list(s.columns) == ["p5", "p50", "p95"]
    np.testing.assert_allclose(s.loc[2100, "p50"], 3.0)
    np.testing.assert_allclose(s.loc[2100, "p5"], np.quantile([1, 2, 3, 4, 5], 0.05))
    np.testing.assert_allclose(s.loc[2100, "p95"], np.quantile([1, 2, 3, 4, 5], 0.95))


def test_summary_custom_quantile_labels(result):
    assert list(result.summary((0.025, 0.17, 0.5)).columns) == ["p2.5", "p17", "p50"]


@pytest.mark.parametrize("bad", [(), (1.5,), (-0.1,)])
def test_summary_rejects_bad_quantiles(result, bad):
    with pytest.raises(ValueError, match="quantiles"):
        result.summary(bad)


def test_background_warming_relative_to_1850_1900():
    years = np.arange(1750, 2101)
    temps = np.where(years >= 1850, 1.0, 0.0)[:, None].repeat(3, axis=1)
    temps[years > 1901] = 2.0
    r = ContributionResult(years, np.arange(3), temps, temps)
    bw = r.background_warming()
    # baseline = weighted mean of timebounds 1850..1901, all 1.0 here
    np.testing.assert_allclose(bw.loc[2000, "p50"], 1.0)
    np.testing.assert_allclose(bw.loc[1900, "p50"], 0.0)


def test_background_warming_uses_half_weights_at_baseline_ends():
    years = np.arange(1750, 2101)
    temps = np.zeros((years.size, 1))
    temps[years == 1850] = 52.0  # half weight of 52 over total weight 51 -> 26/51
    r = ContributionResult(years, np.arange(1), temps, temps)
    np.testing.assert_allclose(r.background_warming().loc[2000, "p50"], -26.0 / 51.0)


def test_plot_returns_axes_with_median_and_band(result):
    ax = result.plot()
    assert ax.get_ylabel().startswith("Temperature")
    assert "ssp245" in ax.get_title()
    assert len(ax.lines) == 2  # median + zero line
    assert len(ax.collections) == 1  # 5-95 % band


def test_repr_is_short_and_informative(result):
    text = repr(result)
    assert len(text) < 300
    assert "ssp245" in text and "5 members" in text and "1750-2100" in text


def test_plot_starts_shortly_before_first_emission_year():
    years = np.arange(1750, 2101)
    temps = np.zeros((years.size, 2))
    md = {"first_emission_year": 2025}
    ax = ContributionResult(years, np.arange(2), temps, temps, metadata=md).plot()
    assert ax.get_xlim()[0] == 2015
    assert ax.lines[0].get_xdata()[0] == 2015


def test_plot_start_year_can_be_overridden(result):
    ax = result.plot(start_year=1900)
    assert ax.get_xlim()[0] == 1900


def test_default_method_is_leave_one_out(result):
    assert result.method == "leave_one_out"


@pytest.mark.parametrize(
    "method,reference", [("leave_one_out", "with"), ("add", "without")]
)
def test_background_warming_uses_the_unmodified_ssp_run(method, reference):
    # leave_one_out: "with" is the real world (SSP); add: "without" is the SSP.
    years = np.arange(1750, 2101)
    ssp = np.where(years > 1901, 1.0, 0.0)[:, None]
    other = np.where(years > 1901, 5.0, 0.0)[:, None]
    runs = (
        {"with": ssp, "without": other}
        if reference == "with"
        else {"with": other, "without": ssp}
    )
    r = ContributionResult(
        years, np.arange(1), runs["with"], runs["without"], method=method
    )
    np.testing.assert_allclose(r.background_warming().loc[2000, "p50"], 1.0)


def test_repr_names_the_method(result):
    assert "leave_one_out" in repr(result)
