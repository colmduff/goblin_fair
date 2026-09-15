import re

import pytest

from goblin_fair import _data


def _recorded_checksums() -> dict[str, str]:
    text = _data.data_path("DATA_SOURCES.md").read_text(encoding="utf-8")
    pattern = r"^\| `([\w.\-]+\.csv)` \| `([0-9a-f]{64})` \|$"
    return dict(re.findall(pattern, text, re.M))


def test_every_bundled_file_is_documented_with_matching_sha256():
    recorded = _recorded_checksums()
    assert set(recorded) == set(_data.DATA_FILES)
    for name in _data.DATA_FILES:
        assert _data.file_sha256(_data.data_path(name)) == recorded[name], name


def test_load_parameters_all_members():
    p = _data.load_parameters()
    assert len(p) == 841
    assert "forcing_scale[Solar]" in p.columns


def test_load_parameters_first_n_members():
    p = _data.load_parameters(5)
    assert list(p.index) == list(_data.load_parameters().index[:5])


def test_load_parameters_explicit_members_keeps_order():
    ids = list(_data.load_parameters().index[[3, 0]])
    assert list(_data.load_parameters(ids).index) == ids


@pytest.mark.parametrize("bad", [0, 842, -1, [999_999_999], [], True, 2.5, "10"])
def test_load_parameters_rejects_invalid_members(bad):
    with pytest.raises(ValueError, match="members"):
        _data.load_parameters(bad)


def test_load_forcing_covers_run_period():
    f = _data.load_forcing()
    assert f.index[0] == 1750 and f.index[-1] == 2500
    assert list(f.columns) == ["Solar", "Volcanic"]
    assert not f.isna().any().any()


def test_load_background_is_fair_csv_format():
    bg = _data.load_background("ssp245")
    assert list(bg.columns[:4]) == ["scenario", "region", "variable", "unit"]
    assert set(bg["scenario"]) == {"ssp245"}
    assert {"CO2 FFI", "CO2 AFOLU", "CH4", "N2O", "Sulfur"} <= set(bg["variable"])
    assert bg.shape[0] == 51
    assert not bg.iloc[:, 4:].isna().any().any()


def test_load_background_rejects_unknown():
    with pytest.raises(ValueError, match="ssp245"):
        _data.load_background("ssp999")


def test_backgrounds_are_the_eight_ssps():
    assert _data.BACKGROUNDS == (
        "ssp119",
        "ssp126",
        "ssp245",
        "ssp370",
        "ssp434",
        "ssp460",
        "ssp534-over",
        "ssp585",
    )
