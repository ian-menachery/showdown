"""Gate P, the preflop model (DECISIONS 34): the bars on the committed DECISIONS 34 model.

Pinned to that model (DECISIONS 49): `data/preflop_model_v1.json` once the re-solve moves it
there, `data/preflop_model.json` until then. Bar 4, the independent payoff check, and
recomputed exploitability are in test_gate_p_slow.py.
"""

import hashlib
from pathlib import Path

import pytest

from showdown import preflop_model as pm
from showdown import pushfold as pf
from showdown.equity.cards import CLASS_NAMES

ROOT = Path(__file__).resolve().parents[1]
MODEL = pm.v1_model_path()


@pytest.fixture(scope="module")
def model() -> pm.PreflopModel:
    return pm.PreflopModel.load(MODEL)


def test_the_pre_registered_solve(model) -> None:
    assert model.version == 1
    assert model.iterations == 1000
    assert model.matrix_path == "data/preflop_169_exact.npz"
    digest = hashlib.sha256((ROOT / model.matrix_path).read_bytes()).hexdigest()
    assert model.matrix_sha256 == digest
    got = sorted((s.stack, s.r_oop) for s in model.solutions)
    assert got == sorted((float(g), r) for r in pm.R_VALUES for g in pm.GRID)
    assert all(s.raises for s in model.solutions)
    assert [(c.stack, c.r_oop, c.raises) for c in model.checks] == [
        (20.0, 0.9, False),
        (20.0, 0.9, True),
    ]


def test_bar1_exploitability_at_every_depth(model) -> None:
    worst = max(s.exploitability for s in model.solutions)
    assert worst <= 1e-3, worst


def test_bar2_continuity_with_push_fold(model) -> None:
    jam_only = model.checks[0]
    pushfold = pf.PushFoldSolution.load(ROOT / "data" / "pushfold.json").at(20)
    for k, name in enumerate(CLASS_NAMES):
        push = dict(zip(jam_only.actions[""], jam_only.strategy[""][name], strict=True))
        call = dict(zip(jam_only.actions["j"], jam_only.strategy["j"][name], strict=True))
        assert push["all-in"] == pushfold.push[k], name
        assert call["call"] == pushfold.call[k], name
    assert jam_only.exploitability == pushfold.exploitability


def test_bar3_sanity_at_20_bb(model) -> None:
    full = model.checks[1]
    pushfold = pf.PushFoldSolution.load(ROOT / "data" / "pushfold.json").at(20)
    bound = pushfold.value_sb - (full.exploitability + pushfold.exploitability)
    assert full.value_sb >= bound, (full.value_sb, bound)
