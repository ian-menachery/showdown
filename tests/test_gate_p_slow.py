"""Gate P, the slow bars (DECISIONS 34): the independent payoff check (bar 4) and
recomputed exploitability. Run with `py gate.py --full`.
"""

from pathlib import Path

import pytest

from showdown import preflop_model as pm
from showdown.cfr import compile_game, exploitability
from showdown.equity.matrix import PreflopMatrix
from showdown.games.base import CHANCE, TERMINAL
from showdown.games.preflop import PreflopGame

pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "data" / "preflop_169_exact.npz"
CODE = "fcrj"


def closed_form(history: str, e: float, stack: float, r_oop: float) -> float:
    """The SB's net in bb at a terminal, written from DECISIONS 34's rules alone.

    It tracks each player's contribution. A fold loses the folder's
    contribution. A call of an all-in pays S(2E − 1). A call of a raise or
    3-bet pays c(2·share − 1), with share = 1 − R(1 − E).
    """
    put_in = [0.5, 1.0]  # SB, BB
    facing_allin = False
    for k, action in enumerate(history):
        me, other = k % 2, 1 - k % 2
        if action == "f":
            return -put_in[0] if me == 0 else put_in[1]
        if action == "r":
            put_in[me] = 2.5 if k == 0 else 3 * 2.5
        elif action == "j":
            put_in[me] = stack
            facing_allin = True
        elif action == "c":
            put_in[me] = put_in[other]
            if facing_allin:
                return stack * (2 * e - 1)
            share = 1 - r_oop * (1 - e)
            return put_in[0] * (2 * share - 1)
    raise AssertionError(f"{history!r} is not terminal")


@pytest.mark.parametrize("stack", [25.0, 100.0])
@pytest.mark.parametrize("r_oop", list(pm.R_VALUES))
def test_bar4_every_terminal_matches_the_closed_form(stack, r_oop) -> None:
    matrix = PreflopMatrix.load(MATRIX)
    tree = compile_game(PreflopGame(stack, matrix, r_oop=r_oop))
    assert tree.player[0] == CHANCE
    checked = 0
    for deal, child in zip(tree.labels[0], tree.children[0], strict=True):
        i, j = divmod(deal, 169)
        e = float(matrix.equity[i, j])
        stack_ = [(child, "")]
        while stack_:
            node, history = stack_.pop()
            if tree.player[node] == TERMINAL:
                want = closed_form(history, e, stack, r_oop)
                assert tree.utility[node] == pytest.approx(want, abs=1e-12), (deal, history)
                checked += 1
                continue
            for action, nxt in zip(tree.labels[node], tree.children[node], strict=True):
                stack_.append((nxt, history + CODE[action]))
    # 11 terminals per deal: f, rf, rc, rrf, rrc, rrjf, rrjc, rjf, rjc, jf, jc.
    assert checked == 169 * 169 * 11


@pytest.mark.parametrize("stack", [25.0, 100.0])
def test_stored_exploitability_matches_a_fresh_best_response(stack) -> None:
    model = pm.PreflopModel.load(ROOT / "data" / "preflop_model.json")
    s = model.at(stack, pm.R_PRODUCT)
    tree = compile_game(PreflopGame(stack, PreflopMatrix.load(MATRIX), r_oop=s.r_oop))
    policy = []
    for key in tree.infoset_key:
        _, name, node = key.split(":")
        policy.append(list(s.strategy[node][name]))
    assert exploitability(tree, policy) == pytest.approx(s.exploitability, abs=1e-12)
