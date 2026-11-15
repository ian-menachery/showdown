"""Gate F, the fast bullets: a hand-built fixture of 34 hands (31 PHH, 3 PokerStars
text) with every stat counted by hand, all-in EV adjustment against hand-computed
values to 1e-6 bb, and push/fold grading (SCOPE, DECISIONS 25 to 27).

The expected values in tests/fixtures/hh/expected.toml were written before the
analyzer ran on these hands, with the counting in a comment per hand.
"""

import tomllib
from pathlib import Path

import pytest

from showdown.bot.policy import PushFoldStrategy
from showdown.cli import main
from showdown.equity.cards import CLASS_NAMES
from showdown.hh.grade import depth_for, grade_hand
from showdown.hh.parse import load, load_phh, load_pokerstars
from showdown.hh.stats import analyze

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "hh"
EXPECTED = tomllib.loads((FIXTURE / "expected.toml").read_text(encoding="utf-8"))
FLAGS = {
    "opp": lambda p: int(p.preflop_decisions > 0),
    "vpip": lambda p: int(p.vpip),
    "pfr": lambda p: int(p.pfr),
    "tbc": lambda p: int(p.three_bet_chance),
    "tb": lambda p: int(p.three_bet),
    "flop": lambda p: int(p.saw_flop),
    "sd": lambda p: int(p.showdown),
    "wsd": lambda p: int(p.won_at_showdown),
}
EV_TOLERANCE_BB = 1e-6


def _key(source: str) -> str:
    path, _, index = source.partition("#")
    name = Path(path).name
    return f"{name}#{index}" if index else Path(name).stem


@pytest.fixture(scope="module")
def parsed():
    return load([FIXTURE])


@pytest.fixture(scope="module")
def records(parsed):
    return {_key(r.source): r for r in parsed.records}


@pytest.fixture(scope="module")
def analysis(parsed):
    return analyze(parsed.records)


def test_every_fixture_hand_parses(parsed, records) -> None:
    assert parsed.found == 34
    assert parsed.parsed == 34
    assert parsed.failures == []
    assert set(records) == set(EXPECTED)
    assert len(EXPECTED) >= 30


@pytest.mark.parametrize("hand", sorted(EXPECTED))
def test_every_stat_matches_the_hand_count(records, hand) -> None:
    record = records[hand]
    expected = EXPECTED[hand]
    assert sorted(p.name for p in record.players) == sorted(
        k for k in expected if k not in ("ev", "grade")
    )
    for p in record.players:
        want = expected[p.name]
        for flag, read in FLAGS.items():
            assert read(p) == want[flag], (hand, p.name, flag)
        assert p.net == pytest.approx(want["net"], abs=1e-9), (hand, p.name)


def test_player_totals_are_the_sums_of_the_hand_counts(analysis, records) -> None:
    report, _ = analysis
    for name, s in report.players.items():
        rows = [(h, EXPECTED[h][name], records[h]) for h in EXPECTED if name in EXPECTED[h]]
        assert s.hands == len(rows)
        assert s.opportunities == sum(r["opp"] for _, r, _ in rows)
        assert s.vpip == sum(r["vpip"] for _, r, _ in rows)
        assert s.pfr == sum(r["pfr"] for _, r, _ in rows)
        assert s.three_bet_chances == sum(r["tbc"] for _, r, _ in rows)
        assert s.three_bets == sum(r["tb"] for _, r, _ in rows)
        assert s.saw_flop == sum(r["flop"] for _, r, _ in rows)
        assert s.wtsd == sum(r["sd"] for _, r, _ in rows)
        assert s.won_at_showdown == sum(r["wsd"] for _, r, _ in rows)
        net_bb = sum(r["net"] / rec.big_blind for _, r, rec in rows)
        assert s.net_bb == pytest.approx(net_bb, abs=1e-9)
        assert s.bb_per_100 == pytest.approx(100 * net_bb / len(rows), abs=1e-9)


def test_allin_ev_matches_the_hand_computed_values(analysis, records) -> None:
    report, adjustments = analysis
    hands_with_ev = [h for h in EXPECTED if "ev" in EXPECTED[h]]
    assert len(hands_with_ev) == 8
    assert report.allin_hands == 8
    assert report.allin_exact == 8
    assert report.allin_multiway == 1
    assert set(adjustments) == {records[h].source for h in hands_with_ev}
    for hand in hands_with_ev:
        record = records[hand]
        adjustment = adjustments[record.source]
        names = [p.name for p in record.players]
        assert adjustment.method == "exact"
        for name, chips in EXPECTED[hand]["ev"].items():
            got = adjustment.ev_net[names.index(name)]
            assert abs(got - chips) / record.big_blind <= EV_TOLERANCE_BB, (hand, name)
        assert sum(adjustment.ev_net.values()) == pytest.approx(0, abs=1e-9)


def test_ev_adjusted_totals(analysis, records) -> None:
    report, adjustments = analysis
    for name, s in report.players.items():
        total = 0.0
        for hand, want in EXPECTED.items():
            if name not in want:
                continue
            chips = want.get("ev", {}).get(name, want[name]["net"])
            total += chips / records[hand].big_blind
        assert s.ev_net_bb == pytest.approx(total, abs=1e-6)


@pytest.mark.parametrize("hand", sorted(EXPECTED))
def test_grading_matches_the_hand_count(records, hand) -> None:
    strategy = PushFoldStrategy.load()
    result = grade_hand(records[hand], strategy)
    want = EXPECTED[hand]["grade"]
    if isinstance(want, str):
        assert result.reason == want
        assert result.decisions == ()
        return
    assert result.reason is None
    got = [
        {
            "seat": d.seat,
            "player": d.player,
            "depth": d.depth,
            "class": CLASS_NAMES[d.hand_class],
            "allin": d.allin,
        }
        for d in result.decisions
    ]
    assert got == want
    for d in result.decisions:  # the loss is the trainer's grade for the same decision
        same = strategy.grade(d.depth, d.seat, d.hand_class, d.allin)
        assert d.loss == same.loss


def test_depth_rounding() -> None:
    assert [depth_for(x) for x in (0.4, 1.0, 7.49, 7.5, 19.6, 20.0)] == [1, 1, 7, 8, 20, 20]


def test_failures_are_counted_never_dropped(tmp_path) -> None:
    bad = tmp_path / "bad.phh"
    bad.write_text("variant = 'NT'\nthis is not toml = = =\n", encoding="utf-8")
    report = load_phh(bad)
    assert (report.found, report.parsed, len(report.failures)) == (1, 0, 1)

    wrong = tmp_path / "wrong_stacks.phh"
    text = (FIXTURE / "h04_three_bet_takes_it.phh").read_text(encoding="utf-8")
    wrong.write_text(text.replace("[108, 98, 94]", "[100, 100, 100]"), encoding="utf-8")
    report = load_phh(wrong)
    assert report.parsed == 0
    assert "differ from recorded" in report.failures[0][1]

    odd = tmp_path / "odd_chip.phh"
    odd.write_text(text.replace("[108, 98, 94]", "[107.5, 98.5, 94]"), encoding="utf-8")
    report = load_phh(odd)
    assert report.parsed == 1
    assert report.odd_chip == 1

    stars = tmp_path / "broken.txt"
    stars.write_text("PokerStars Hand #1: this is not a hand\n", encoding="utf-8")
    report = load_pokerstars(stars)
    assert report.found >= 1
    assert report.parsed == 0
    assert len(report.failures) == report.found


def test_analyze_command(capsys) -> None:
    assert main(["analyze", str(FIXTURE), "--player", "Hero", "--player", "Vil"]) == 0
    out = capsys.readouterr().out
    assert "hands found 34, parsed 34 (100.00%)" in out
    assert "Hero" in out
    assert "adjusted 8 exactly" in out
    assert "not gradable, not heads-up: 19" in out
    assert "Hero: 7 decisions, 1 mistakes" in out
    assert main(["analyze", str(FIXTURE / "nothing-here")]) == 1
