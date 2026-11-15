"""Gate F, the slow bullet: at least 99% of the 10,000 phh-dataset Pluribus hands parse,
with every failure counted and printed (SCOPE, DECISIONS 25). Also Done 4: the
analyzer runs on all of them.

Needs data/external/phh (DECISIONS 25). A missing or changed folder fails the run.
"""

import tomllib
from decimal import Decimal

import pytest
from external_data import require_pluribus

from showdown.cli import main
from showdown.hh.parse import load
from showdown.hh.stats import analyze

pytestmark = pytest.mark.slow


def test_pluribus_hands_parse_and_reconcile() -> None:
    root = require_pluribus()
    report = load([root])
    print(f"\nfound {report.found}, parsed {report.parsed}, odd chip {report.odd_chip}")
    for source, reason in report.failures:
        print("FAILED", source, reason)
    assert report.found == 10_000
    assert report.parsed / report.found >= 0.99

    # Pluribus's result from our replay equals the files' own stacks, to the odd chip.
    direct = Decimal(0)
    for path in root.rglob("*.phh"):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        i = data["players"].index("Pluribus")
        finish, start = data["finishing_stacks"][i], data["starting_stacks"][i]
        direct += Decimal(str(finish)) - Decimal(str(start))
    ours = sum(p.net for r in report.records for p in r.players if p.name == "Pluribus")
    assert abs(ours - float(direct)) <= report.odd_chip

    stats, _ = analyze(report.records, samples=2_000)
    pluribus = stats.players["Pluribus"]
    assert pluribus.hands == 10_000
    print(
        f"Pluribus: VPIP {pluribus.vpip_pct:.1f} PFR {pluribus.pfr_pct:.1f} "
        f"3bet {pluribus.three_bet_pct:.1f} WTSD {pluribus.wtsd_pct:.1f} "
        f"W$SD {pluribus.wsd_pct:.1f} bb/100 {pluribus.bb_per_100:.2f} "
        f"EV bb/100 {pluribus.ev_bb_per_100:.2f}"
    )


def test_analyze_command_on_pluribus(capsys) -> None:
    root = require_pluribus()
    assert main(["analyze", str(root), "--player", "Pluribus", "--samples", "2000"]) == 0
    out = capsys.readouterr().out
    assert "hands found 10,000" in out
    assert "Pluribus" in out
