"""PCM-Forge Offline (pcm_forge_offline.py): the desktop app must build the
same sticks as generate_codes.py, and read a returned stick back correctly.
No window is opened: the GUI only wires these functions to buttons."""
import filecmp
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import generate_codes as gc          # noqa: E402
import pcm_forge_offline as app      # noqa: E402

VIN = "WP1AA2A29ELA00000"


def tree(d):
    out = {}
    for root, _dirs, files in os.walk(d):
        for f in files:
            p = os.path.join(root, f)
            out[os.path.relpath(p, d)] = p
    return out


def test_selftest_builds_both_sticks(tmp_path):
    assert app.selftest(str(tmp_path)) == 0
    assert (tmp_path / "selftest.txt").read_text().startswith("OK")


def test_default_model_exists():
    assert app.DEFAULT_MODEL in gc.MODELS
    assert any(k == app.DEFAULT_MODEL for _l, k in app.model_choices())


@pytest.mark.parametrize("model", ["cayenne-se", "911"])
def test_activation_stick_matches_cli(tmp_path, model):
    """All features ticked == the CLI's stick, byte for byte."""
    cli, gui = tmp_path / "cli", tmp_path / "gui"
    subprocess.run([sys.executable, os.path.join(ROOT, "generate_codes.py"), "-q", "-m", model,
                    VIN, str(cli)], check=True, capture_output=True)
    names = {f[0] for f in gc.features_for(gc.MODELS[model][0])}
    app.build_activation(VIN, model, names, str(gui))
    a, b = tree(cli), tree(gui)
    assert set(a) == set(b)
    for rel in a:
        assert filecmp.cmp(a[rel], b[rel], shallow=False), rel


def test_diagnostic_stick_matches_cli(tmp_path):
    cli, gui = tmp_path / "cli", tmp_path / "gui"
    subprocess.run([sys.executable, os.path.join(ROOT, "generate_codes.py"), "--diag", str(cli)],
                   check=True, capture_output=True)
    app.build_diagnostic(str(gui))
    a, b = tree(cli), tree(gui)
    assert set(a) == set(b)
    for rel in a:
        assert filecmp.cmp(a[rel], b[rel], shallow=False), rel


def test_subset_stick_has_only_ticked_features(tmp_path):
    feats = app.build_activation(VIN, "cayenne-se", {"UMS", "BTH"}, str(tmp_path))
    recs = gc.load_records(str(tmp_path / "PagSWAct.002"))
    assert sorted(f[0] for f in feats) == ["BTH", "UMS"]
    assert len(recs) == 2


def test_nothing_ticked_is_refused(tmp_path):
    with pytest.raises(ValueError):
        app.build_activation(VIN, "cayenne-se", set(), str(tmp_path))


def test_returned_stick_round_trip(tmp_path):
    """A diagnostic stick's backup ticks the same features and model back."""
    src = tmp_path / "src"
    app.build_activation(VIN, "cayenne-se", {"ENGINEERING", "UMS", "FeatureLevel"}, str(src))
    stick = tmp_path / "stick"
    (stick / "pcm_dump_20261112").mkdir(parents=True)
    (stick / "PagSWAct_backup_20261112.002").write_bytes((src / "PagSWAct.002").read_bytes())
    (stick / "pcm_dump_20261112" / "vin").write_text(VIN + "\n")

    assert gc.vin_from_diagnostics(str(stick))[0] == VIN
    names, model, kept = app.car_features(str(stick))
    assert names == {"ENGINEERING", "UMS", "FeatureLevel"}
    assert model == "cayenne-se"
    assert kept == []
    rc, text = app.capture(gc.show_pagswact, str(stick), VIN)
    assert rc == 0 and "MATCH" in text


def test_variant_record_is_reported_not_changed(tmp_path):
    rec = gc.build_record(VIN, *next((f[1], f[2]) for f in gc.features_for(0x0043)
                                     if f[0] == "NavDBEurope"), 0x0007)
    (tmp_path / "PagSWAct.002").write_bytes(bytes(rec))
    names, _model, kept = app.car_features(str(tmp_path))
    assert names == {"NavDBEurope"}
    assert kept == ["NavDBEurope variant 0x0007"]


def test_no_backup_on_stick(tmp_path):
    assert app.car_features(str(tmp_path)) is None
