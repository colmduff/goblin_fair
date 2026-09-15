"""Shared pytest fixtures for goblin_fair."""

import pandas as pd
import pytest

import goblin_fair as gf

N_MEMBERS = 5


@pytest.fixture(scope="session")
def co2_pulse_result():
    """10 Gt CO2/yr for 2030-2039 on ssp245, first 5 members, run to 2080."""
    df = pd.DataFrame({"CO2": 10.0}, index=range(2030, 2040))
    return gf.temperature_contribution(df, units="Gt", end_year=2080, members=N_MEMBERS)
