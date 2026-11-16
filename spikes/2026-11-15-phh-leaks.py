r"""Spike, 2026-11-15: how often do real players make the common preflop and flop moves? (DECISIONS 39)

Measures VPIP, PFR, 3-bet, flop continuation bets and folds to them, over the
PHH dataset's online no-limit hands (HandHQ, July 2009). The hands are read
straight from the pinned zip, with nothing extracted. DECISIONS 39's amendment
explains why: these hands record no stacks, so the replay filter and the jam
measures could not apply.

The findings are candidate starting points for Phase 12's opponent model, not
facts about Ian's friends. Writes docs/human-leaks.md. Run from the repo
root:

    .venv\Scripts\python -I spikes\2026-11-15-phh-leaks.py

Not part of the package and not linted by the gate.

Output on Ian's laptop, 2026-11-15, in 790 s. The zip matched Zenodo's md5;
its SHA-256 is 65d566e7a3387b4c3ec28213b5416a8a36a4f4f1cf822771b77f5232fbba3281.
It counted 116,861,965 player-hands, and every hand counted (no failures).

    | Table    | Player-hands | VPIP  | PFR   | 3-bet | Flop c-bet | Fold to flop c-bet |
    | heads-up |    6,109,392 | 49.4% | 33.8% | 14.0% | 63.2%      | 45.3%              |
    | 3-6      |   72,497,321 | 27.1% | 15.2% |  5.8% | 65.0%      | 50.6%              |
    | 7+       |   38,255,252 | 20.2% |  8.8% |  3.3% | 67.9%      | 54.2%              |

Across the 34,301 players with at least 500 hands: median VPIP 25.4%
(quartiles 18.8% and 36.5%), median PFR 12.8%. 19.6% of these players are
loose (VPIP at least 40%), and 13.0% are tight (VPIP at most 15%). The full
tables are in docs/human-leaks.md.
"""

import ast
import hashlib
import re
import statistics
import sys
import time
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ZIP = Path("data/external/phh-zenodo/poker-hand-histories.zip")
SIZE = 20_289_230_983
MD5 = "5a49377ab4ea30db3aa887c8e0ce580f"
PREFIX = "data/handhq/"
NOTE = Path("docs/human-leaks.md")
MIN_HANDS = 500
STAKE = re.compile(r"data/handhq/(?P<site>[A-Z]+)-[^_]+_[^_]+_(?P<stake>\d+)NLH_OBFU/")
COUNTS = ("hands", "vpip", "pfr", "tb_chance", "tb", "cb_chance", "cb", "fcb_chance", "fcb")


def table_size(n: int) -> str:
    return "heads-up" if n == 2 else ("3-6" if n <= 6 else "7+")


def parse_hand(block: dict[str, str]) -> tuple[list[str], list[list[int]]] | str:
    """(players, per-player counts in COUNTS order), or the reason the hand does not count."""
    if block.get("variant") != "'NT'":
        return "not no-limit hold'em"
    try:
        actions = ast.literal_eval(block["actions"])
        players = ast.literal_eval(block["players"])
        blinds = ast.literal_eval(block["blinds_or_straddles"])
    except (KeyError, ValueError, SyntaxError):
        return "a field does not parse"
    n = len(players)
    if n < 2 or len(blinds) != n:
        return "fewer than two players"
    counts = [[0] * len(COUNTS) for _ in range(n)]
    for c in counts:
        c[0] = 1
    contrib = [float(b) for b in blinds]
    level = max(contrib)
    folded = [False] * n
    acted_pre = [False] * n
    tb_seen = [False] * n
    street = 0
    raises = 0
    aggressor = None
    flop_bet_by = None
    flop_raised = False
    faced_cb = [False] * n
    for a in actions:
        t = a.split()
        if not t:
            return "an empty action"
        if t[0] == "d":
            if t[1] == "db":
                street += 1
                contrib, level = [0.0] * n, 0.0
            continue
        if not t[0].startswith("p") or len(t) < 2:
            return f"unknown action {a!r}"
        try:
            i = int(t[0][1:]) - 1
        except ValueError:
            return f"unknown actor {a!r}"
        if not 0 <= i < n or folded[i]:
            return "an action by a player not in the hand"
        act = t[1]
        if act in ("sm", "sd"):
            continue
        if act not in ("f", "cc", "cbr"):
            return f"unknown action {a!r}"
        c = counts[i]
        if street == 0:
            if raises == 1 and not tb_seen[i] and aggressor != i:
                tb_seen[i] = True
                c[3] += 1
                c[4] += act == "cbr"
            if not acted_pre[i]:
                acted_pre[i] = True
                if act == "cbr" or (act == "cc" and contrib[i] < level):
                    c[1] = 1
            if act == "cbr":
                c[2] = 1
                c[1] = 1
        elif street == 1:
            if i == aggressor and flop_bet_by is None:
                c[5] += 1
                if act == "cbr":
                    c[6] += 1
                    flop_bet_by = i
            elif (
                aggressor is not None
                and flop_bet_by == aggressor
                and i != aggressor
                and not flop_raised
                and not faced_cb[i]
            ):
                faced_cb[i] = True
                c[7] += 1
                c[8] += act == "f"
            if act == "cbr" and flop_bet_by is None:
                flop_bet_by = i
            elif act == "cbr" and flop_bet_by is not None and i != flop_bet_by:
                flop_raised = True
        if act == "f":
            folded[i] = True
        elif act == "cc":
            contrib[i] = level
        else:
            try:
                amount = float(t[2])
            except (IndexError, ValueError):
                return f"a bet without an amount {a!r}"
            contrib[i], level = amount, amount
            if street == 0:
                raises += 1
                aggressor = i
    if street == 0:
        for c in counts:  # nobody saw a flop: no flop chances
            c[5:] = [0, 0, 0, 0]
    return players, counts


def blocks(text: str):
    """Yield each hand's top-level `key = value` lines as a dict."""
    block: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("["):
            if block:
                yield block
            block = {}
        elif " = " in line:
            key, value = line.split(" = ", 1)
            block[key] = value
    if block:
        yield block


def folder_job(args: tuple[str, list[str]]) -> tuple[str, dict, dict, Counter]:
    """One site-and-stake folder: (folder, bucket totals, per-player totals, failures)."""
    folder, members = args
    buckets: dict[str, list[int]] = defaultdict(lambda: [0] * len(COUNTS))
    per_player: dict[str, list[int]] = defaultdict(lambda: [0] * len(COUNTS))
    failures: Counter = Counter()
    site = STAKE.match(folder).group("site")
    with zipfile.ZipFile(ZIP) as z:
        for name in members:
            text = z.read(name).decode("utf-8", "replace")
            for block in blocks(text):
                result = parse_hand(block)
                if isinstance(result, str):
                    failures[result] += 1
                    continue
                players, counts = result
                bucket = buckets[table_size(len(players))]
                for p, c in zip(players, counts, strict=True):
                    totals = per_player[f"{site}:{p}"]
                    for k, v in enumerate(c):
                        bucket[k] += v
                        totals[k] += v
    return folder, dict(buckets), dict(per_player), failures


def verify() -> str:
    if ZIP.stat().st_size != SIZE:
        sys.exit("zip size does not match DECISIONS 39")
    md5, sha = hashlib.md5(), hashlib.sha256()
    with open(ZIP, "rb") as f:
        while chunk := f.read(1 << 24):
            md5.update(chunk)
            sha.update(chunk)
    if md5.hexdigest() != MD5:
        sys.exit("zip md5 does not match Zenodo's")
    return sha.hexdigest()


def pct(num: int, den: int) -> str:
    return f"{100 * num / den:.1f}%" if den else "-"


def main() -> int:
    start = time.perf_counter()
    sha = verify()
    print(f"zip verified (md5 {MD5}); SHA-256 {sha}", flush=True)
    by_folder: dict[str, list[str]] = defaultdict(list)
    with zipfile.ZipFile(ZIP) as z:
        for name in z.namelist():
            if name.startswith(PREFIX) and name.endswith(".phhs"):
                by_folder[STAKE.match(name).group(0)].append(name)
    jobs = sorted(by_folder.items(), key=lambda kv: -len(kv[1]))
    totals: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0] * len(COUNTS))
    players: dict[str, list[int]] = defaultdict(lambda: [0] * len(COUNTS))
    failures: Counter = Counter()
    with ProcessPoolExecutor(max_workers=12) as pool:
        for folder, buckets, per_player, fails in pool.map(folder_job, jobs):
            stake = STAKE.match(folder).group("stake")
            for size, c in buckets.items():
                for key in ((size, stake), (size, "all")):
                    totals[key] = [a + b for a, b in zip(totals[key], c, strict=True)]
            for p, c in per_player.items():
                players[p] = [a + b for a, b in zip(players[p], c, strict=True)]
            failures += fails
            print(f"  {folder}: done", flush=True)

    counted = sum(totals[(s, "all")][0] for s in ("heads-up", "3-6", "7+"))
    seats = counted  # one count per player per hand
    hands_failed = sum(failures.values())
    lines = [
        "# How often real players make the common moves (DECISIONS 39)",
        "",
        "**Read this first:** these are 2009 real-money online hands, mostly 6-max, "
        "from the PHH dataset. Heads-up play-money games with friends will differ. "
        "They are candidate starting points for Phase 12's opponent model, not "
        "facts about anyone Ian plays.",
        "",
        'Source: "A Dataset of Poker Hand Histories", Juho Kim, Zenodo, '
        "DOI 10.5281/zenodo.17136841, CC BY 4.0. The online hands are its "
        "`data/handhq/` folder (HandHQ, July 2009, obfuscated player names). "
        "Nothing from it is committed.",
        "",
        f"Zip SHA-256: `{sha}`. Spike: `spikes/2026-11-15-phh-leaks.py`.",
        "",
        f"Counted: {seats:,} player-hands. Hands that did not count: {hands_failed:,} "
        f"({', '.join(f'{k}: {v:,}' for k, v in failures.most_common()) or 'none'}).",
        "",
        "## By table size",
        "",
        "| Table | Player-hands | VPIP | PFR | 3-bet | Flop c-bet | Fold to flop c-bet |",
        "|---|---|---|---|---|---|---|",
    ]
    for size in ("heads-up", "3-6", "7+"):
        c = totals[(size, "all")]
        lines.append(
            f"| {size} | {c[0]:,} | {pct(c[1], c[0])} | {pct(c[2], c[0])} | "
            f"{pct(c[4], c[3])} ({c[3]:,}) | {pct(c[6], c[5])} ({c[5]:,}) | "
            f"{pct(c[8], c[7])} ({c[7]:,}) |"
        )
    lines += [
        "",
        "Rates in brackets give the number of chances.",
        "",
        "## By stake, 3-6 handed",
        "",
        "| Stake | Player-hands | VPIP | PFR | 3-bet | Flop c-bet | Fold to flop c-bet |",
        "|---|---|---|---|---|---|---|",
    ]
    for stake in sorted({k[1] for k in totals if k[1] != "all"}, key=int):
        c = totals.get(("3-6", stake))
        if c and c[0]:
            lines.append(
                f"| {stake}NL | {c[0]:,} | {pct(c[1], c[0])} | {pct(c[2], c[0])} | "
                f"{pct(c[4], c[3])} | {pct(c[6], c[5])} | {pct(c[8], c[7])} |"
            )
    regulars = {p: c for p, c in players.items() if c[0] >= MIN_HANDS}
    vpip = [100 * c[1] / c[0] for c in regulars.values()]
    pfr = [100 * c[2] / c[0] for c in regulars.values()]
    if len(vpip) >= 4:
        vq, pq = statistics.quantiles(vpip, n=4), statistics.quantiles(pfr, n=4)
        loose = sum(v >= 40 for v in vpip) / len(vpip)
        tight = sum(v <= 15 for v in vpip) / len(vpip)
        lines += [
            "",
            f"## Across players with at least {MIN_HANDS} hands",
            "",
            f"{len(regulars):,} players (of {len(players):,} seen).",
            "",
            "| | 25th percentile | Median | 75th percentile |",
            "|---|---|---|---|",
            f"| VPIP | {vq[0]:.1f}% | {vq[1]:.1f}% | {vq[2]:.1f}% |",
            f"| PFR | {pq[0]:.1f}% | {pq[1]:.1f}% | {pq[2]:.1f}% |",
            "",
            f"VPIP at least 40% (loose): {loose:.1%} of these players. "
            f"VPIP at most 15% (tight): {tight:.1%}.",
        ]
    lines += [
        "",
        "## Definitions (DECISIONS 39, amended)",
        "",
        "- **VPIP:** the first voluntary preflop action is a call with chips owed, or "
        "a raise. The big blind checking is not VPIP.",
        "- **PFR:** raises preflop.",
        "- **3-bet:** facing exactly one preflop raise, raises.",
        "- **Flop c-bet:** the last preflop raiser sees the flop and acts before anyone "
        "bets; it bets.",
        "- **Fold to flop c-bet:** facing that bet, before any raise of it, the first "
        "action is a fold.",
        "",
        f"Runtime: {time.perf_counter() - start:.0f} s.",
        "",
    ]
    NOTE.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
