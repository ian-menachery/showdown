"""The six-max drill trainer's pieces and `showdown sixmax drill` (DECISIONS 55)."""

import json

import numpy as np
import pytest

from showdown import sixmax as S
from showdown import sixmax_drill as D
from showdown.cli import main


def _answer(flips) -> S.Answer:
    return S.Answer(
        hand="AA",
        actions=["fold", "limp", "open to 2.5", "open to 3"],
        ev=np.array([0.0, 0.2, 1.0, 0.8]),
        se=np.zeros(4),
        best="open to 2.5",
        runner_up="open to 3",
        gap_se=5.0,
        tier="close",
        flips=flips,
        no_stackoff_best="open to 2.5",
    )


def test_grade() -> None:
    a = _answer([(0.1, -0.1, "limp")])
    assert D.grade(a, "raise") == ("good", 0.0)
    assert D.grade(a, "limp") == ("marginal", pytest.approx(0.8))
    assert D.grade(a, "fold") == ("review", pytest.approx(1.0))
    assert D.grade(_answer([]), "limp") == ("review", pytest.approx(0.8))
    assert len(D.SHAPES) == 17
    over = _answer([])
    over.actions = ["fold", "overlimp", "iso to 4", "iso to 5"]
    assert D._prompt(over) == (
        "Your action? [f]old / over[l]imp / [r]aise / [q]uit: ",
        ["fold", "limp", "raise"],
    )


def test_a_session_logs_and_sums(tmp_path) -> None:
    std = S.load_profiles()["standard"]
    trainer = D.Trainer(std, ante=0.5, samples=1_500, seed=3)
    replies = iter(["x", "f", "r", "l", "q"])
    shown = []

    def ask(prompt: str) -> str:
        reply = next(replies)
        if reply == "f" and "[f]old" not in prompt:
            reply = "r"  # the BB has no fold
        return reply

    summary = D.run(trainer, 10, log_dir=tmp_path, ask=ask, show=shown.append)
    text = "\n".join(shown)
    assert "Answer" in text and "Drill 4 of 10" in text and "Session: 3 drills" in text
    with open(summary["log"], encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    assert len(rows) == summary["drills"] == 3
    assert all(r["ante"] == 0.5 and r["profile"] == "standard" for r in rows)
    assert sum(summary["grades"].values()) == 3
    assert summary["bb_lost"] == pytest.approx(sum(r["bb_lost"] for r in rows))
    for r in rows:
        assert r["grade"] == "good" or r["bb_lost"] >= 0


def test_the_command(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(D, "LOG_DIR", tmp_path)
    monkeypatch.setattr("builtins.input", lambda prompt: "r")
    assert main(["sixmax", "drill", "--count", "2", "--samples", "1500", "--seed", "5"]) == 0
    out = capsys.readouterr().out
    assert "Drill 2 of 2" in out and "Session: 2 drills" in out
    assert len(list(tmp_path.glob("*.jsonl"))) == 1
    with pytest.raises(SystemExit, match="give a hand"):
        main(["sixmax", "BTN"])
