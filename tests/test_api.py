import pandas as pd
import pytest

import goblin_fair as gf


def test_public_names():
    assert set(gf.__all__) == {
        "temperature_contribution",
        "ContributionResult",
        "list_backgrounds",
        "__version__",
    }


def test_list_backgrounds():
    assert gf.list_backgrounds() == [
        "ssp119",
        "ssp126",
        "ssp245",
        "ssp370",
        "ssp434",
        "ssp460",
        "ssp534-over",
        "ssp585",
    ]


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"background": "rcp45"}, "ssp245"),
        ({"end_year": 1901}, "1902"),
        ({"end_year": 2501}, "2500"),
        ({"end_year": 2100.0}, "end_year"),
        ({"members": 0}, "members"),
        ({"units": "kt CO2e"}, "gas-specific"),
    ],
)
def test_invalid_arguments_fail_before_running_fair(monkeypatch, kwargs, match):
    from goblin_fair import engine

    def must_not_run(*args, **kwargs):
        raise AssertionError("FaIR should not run for invalid arguments")

    monkeypatch.setattr(engine, "run_pair", must_not_run)
    df = pd.DataFrame({"CH4": [1.0]}, index=[2030])
    with pytest.raises(ValueError, match=match):
        gf.temperature_contribution(df, **kwargs)
