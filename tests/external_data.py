"""Third-party reference files in the gitignored data/external/ (DECISIONS 20).

A test that needs one of these fails, never skips, when the file is missing or
its SHA-256 differs from the pinned one. The fetch commands are in
docs/gate-d-reference.md, under "What the files turned out to contain".
"""

import hashlib
from pathlib import Path

import numpy as np
import pytest

from showdown.equity.cards import ALL_COMBOS

EXTERNAL = Path(__file__).resolve().parents[1] / "data" / "external"
SHA256 = {
    "hrc/holdemresources_hu_equilibrium.zip": (
        "650da7525b35e12adbc03df26d6690c30b583ff4b7d930156c104012a040ec9d"
    ),
    "hrc/raw/holdemresources_hu_push.csv": (
        "ed588eda85842704adeb233e7f2a22331aa6b83543b23fce838788ba55e32cc2"
    ),
    "hrc/raw/holdemresources_hu_call.csv": (
        "fa99898839ca9da23bb6193bdfcb873632fecc95b34079b79ff27670426682d3"
    ),
    # HoldemResources' heads-up Nash page, saved 2026-11-19 for its "Ante 10%" chart
    # (DECISIONS 48): curl -s -A "Mozilla/5.0" -o <this path> https://www.holdemresources.net/hune
    "holdemresources/hune.html": (
        "432658557afbb34c97db823daeb627cfa5d7e316ba29ccbdece6ff7607196d87"
    ),
    "b-inary/heads_up_pre_flop_equity.bin": (
        "006404b36d257fc9455da0d0f0ab89aef3e80ece56c8f3e770bad926cfe5ec8a"
    ),
    "texassolver/TexasSolver-v0.2.0-Windows.zip": (
        "0a9122fa0cd9384e6c1cbe0492e8a3b8ac7809890c649e1a53f77a59d6d50a7c"
    ),
    # 20.3 GB: verified in chunks by spikes/2026-11-15-phh-leaks.py, never by require()
    # (DECISIONS 39).
    "phh-zenodo/poker-hand-histories.zip": (
        "65d566e7a3387b4c3ec28213b5416a8a36a4f4f1cf822771b77f5232fbba3281"
    ),
}


def require(relative: str) -> Path:
    """The path of a pinned external file, or a test failure saying how to fetch it."""
    path = EXTERNAL / relative
    if not path.exists():
        pytest.fail(
            f"{path} is missing. Fetch it with the commands in docs/gate-d-reference.md "
            "('What the files turned out to contain'); DECISIONS 20."
        )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != SHA256[relative]:
        pytest.fail(f"{path}: SHA-256 {digest} is not the pinned {SHA256[relative]}")
    return path


PLURIBUS = EXTERNAL / "phh" / "repo" / "data" / "pluribus"
PLURIBUS_MANIFEST = "9903a6146e6939470e9fec1a3e9984306d8980bcea70f1cef36182151f88e58d"
"""SHA-256 of "<relative path> <file SHA-256>" lines, sorted by path (DECISIONS 25)."""


def require_pluribus() -> Path:
    """The pinned phh-dataset Pluribus folder, or a test failure saying how to fetch it."""
    if not PLURIBUS.is_dir():
        pytest.fail(
            f"{PLURIBUS} is missing. Fetch it with the commands in docs/gate-d-reference.md "
            "('Pluribus hands'); DECISIONS 25."
        )
    files = sorted(PLURIBUS.rglob("*.phh"), key=lambda p: p.relative_to(PLURIBUS).as_posix())
    lines = "".join(
        f"{p.relative_to(PLURIBUS).as_posix()} {hashlib.sha256(p.read_bytes()).hexdigest()}\n"
        for p in files
    )
    digest = hashlib.sha256(lines.encode()).hexdigest()
    if digest != PLURIBUS_MANIFEST:
        pytest.fail(f"{PLURIBUS}: manifest {digest} is not the pinned {PLURIBUS_MANIFEST}")
    return PLURIBUS


def binary_equity_numerators() -> np.ndarray:
    """b-inary/poker-cfr's exact table as a 1326 x 1326 int64 array in ALL_COMBOS order.

    Entry [a, b] is 2 * wins + ties for combo a against combo b over all C(48, 5)
    boards, and 0 when the two combos share a card. The file is a bincode
    Vec<u32>: an 8-byte little-endian length, then the entries.
    """
    raw = require("b-inary/heads_up_pre_flop_equity.bin").read_bytes()
    table = np.frombuffer(raw, dtype="<u4", offset=8)
    if int.from_bytes(raw[:8], "little") != table.size or table.size != 1326 * 1326:
        raise AssertionError("unexpected b-inary table layout")
    # Their combo index: cards i < j in lexicographic order. Ours: (high, low).
    order = np.array([(103 - lo) * lo // 2 + (hi - lo - 1) for hi, lo in ALL_COMBOS])
    return table.reshape(1326, 1326).astype(np.int64)[np.ix_(order, order)]
