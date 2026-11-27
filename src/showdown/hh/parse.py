"""Load hand histories through pokerkit: PHH files and PokerStars text (DECISIONS 4, 25).

Every hand either becomes a HandRecord or a counted failure with its reason.
Nothing is dropped silently (Gate F).
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from pokerkit import HandHistory, PokerStarsParser

from showdown.hh.replay import HandRecord, ReplayError, replay


@dataclass
class ParseReport:
    found: int = 0
    records: list[HandRecord] = field(default_factory=list)
    failures: list[tuple[str, str]] = field(default_factory=list)
    """(source, reason) for every hand that did not become a record."""

    @property
    def parsed(self) -> int:
        return len(self.records)

    @property
    def odd_chip(self) -> int:
        return sum(r.odd_chip for r in self.records)

    def add(self, other: ParseReport) -> None:
        self.found += other.found
        self.records += other.records
        self.failures += other.failures


def _replay_into(report: ParseReport, hh: HandHistory, source: str) -> None:
    try:
        report.records.append(replay(hh, source))
    except ReplayError as error:
        report.failures.append((source, str(error)))


def load_phh(path: str | Path) -> ParseReport:
    """One PHH file (one hand per file, as in the phh-dataset)."""
    report = ParseReport(found=1)
    source = str(path)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with open(path, "rb") as f:
                hh = HandHistory.load(f)
    except Exception as error:  # pokerkit raises several types on malformed files
        report.failures.append((source, f"could not load: {error}"))
        return report
    _replay_into(report, hh, source)
    return report


def load_pokerstars(path: str | Path) -> ParseReport:
    """A PokerStars text export: many hands per file, separated by blank lines."""
    return parse_pokerstars(Path(path).read_text(encoding="utf-8-sig"), str(path))


def parse_pokerstars(text: str, path: str) -> ParseReport:
    """PokerStars text already in memory (the play page's Review tab, DECISIONS 63)."""
    text = text.lstrip("﻿").replace("\r\n", "\n")
    report = ParseReport()
    parser = PokerStarsParser()
    histories = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        generator = parser(text)
        while True:
            try:
                histories.append(next(generator))
            except StopIteration as stop:
                found = stop.value or 0
                break
            except Exception as error:  # a malformed hand: counted, then stop reading
                report.failures.append((f"{path}#?", f"could not parse: {error}"))
                found = len(histories) + 1
                break
    report.found = max(found, len(histories))
    skipped = report.found - len(histories) - len(report.failures)
    for k in range(skipped):
        report.failures.append((f"{path}#skipped{k + 1}", "pokerkit's parser skipped it"))
    for k, hh in enumerate(histories):
        _replay_into(report, hh, f"{path}#{k + 1}")
    return report


def load(paths: Iterable[str | Path], fmt: str = "auto") -> ParseReport:
    """Load files and directories (searched recursively for .phh and .txt)."""
    report = ParseReport()
    for path in paths:
        path = Path(path)
        files = sorted(path.rglob("*")) if path.is_dir() else [path]
        for f in files:
            if not f.is_file():
                continue
            kind = fmt
            if kind == "auto":
                kind = {".phh": "phh", ".txt": "pokerstars"}.get(f.suffix.lower())
            if kind == "phh":
                report.add(load_phh(f))
            elif kind == "pokerstars":
                report.add(load_pokerstars(f))
    return report
