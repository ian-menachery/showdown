r"""Spike, 2026-11-22: the six-max profiles' frequencies, fitted to the PHH hands (DECISIONS 53).

Reads DECISIONS 39's zip straight from disk: the HandHQ no-limit hands with 3 to 6
players, all stakes, no antes. Players with at least 500 such hands are bucketed by their
own VPIP and PFR (tight, regular, loose-passive), and six preflop situations are counted
by the acting player's bucket. DECISIONS 53 fixes the buckets, the counts and how they
become the engine's rates, before this script ran.

Writes data/sixmax_profiles.json (the engine's input) and docs/sixmax-profiles.md. Both
hold aggregates only. Run from the repo root:

    .venv\Scripts\python -I spikes\2026-11-22-phh-sixmax-profiles.py

Not part of the package and not linted by the gate.
"""

import ast
import hashlib
import json
import re
import sys
import time
import zipfile
from array import array
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ZIP = Path("data/external/phh-zenodo/poker-hand-histories.zip")
SIZE = 20_289_230_983
SHA256 = "65d566e7a3387b4c3ec28213b5416a8a36a4f4f1cf822771b77f5232fbba3281"
PREFIX = "data/handhq/"
OUT_JSON = Path("data/sixmax_profiles.json")
OUT_DOC = Path("docs/sixmax-profiles.md")
MIN_HANDS = 500
MIN_CHANCES = 1_000
STAKE = re.compile(r"data/handhq/(?P<site>[A-Z]+)-[^_]+_[^_]+_(?P<stake>\d+)NLH_OBFU/")

ISO_EDGES = (3.5, 4.5, 5.5)  # m = raise-to minus limpers, in bb
OPEN_EDGES = (2.75, 3.25, 3.75)  # open size in bb
ISO_REF, OPEN_REF = 1, 1  # the bucket index holding the engine's reference size

# Per-player counters, one flat array of doubles.
HANDS, VPIP, PFR = 0, 1, 2
E1 = 3  # first in: fold, limp, raise
E2 = 6  # facing limpers: fold, overlimp, raise
E3 = 9  # limper facing one raise: 4 buckets x (fold, call, re-raise), then 4 sums of m
E4_SB = 25  # SB facing one open: 4 buckets x (fold, call, 3-bet), then 4 sums of size
E4_BB = 41  # the same for the BB
E5 = 57  # non-blind facing one open: fold, call, 3-bet
E6_SB = 60  # SB facing limpers: fold, complete, raise
E6_BB = 63  # BB facing limpers: check, raise
WIDTH = 65


def bucket(value: float, edges: tuple[float, ...]) -> int:
    return sum(value >= e for e in edges)


def parse_hand(block: dict[str, str]) -> tuple[list[str], list[list[tuple[int, float]]]] | str:
    """(players, per player a list of (counter index, amount to add)), or why it doesn't count."""
    if block.get("variant") != "'NT'":
        return "not no-limit hold'em"
    try:
        actions = ast.literal_eval(block["actions"])
        players = ast.literal_eval(block["players"])
        blinds = [float(b) for b in ast.literal_eval(block["blinds_or_straddles"])]
        antes = [float(a) for a in ast.literal_eval(block.get("antes", "[]"))]
    except (KeyError, ValueError, SyntaxError):
        return "a field does not parse"
    n = len(players)
    if not 3 <= n <= 6:
        return "not 3 to 6 players"
    if any(antes):
        return "antes"
    if len(blinds) != n or not 0 < blinds[0] < blinds[1] or any(blinds[2:]):
        return "not one small and one big blind"
    bb = blinds[1]
    adds: list[list[tuple[int, float]]] = [[(HANDS, 1.0)] for _ in range(n)]
    contrib = list(blinds)
    level = bb
    raises = 0
    limpers: list[int] = []
    limpers_at_raise = 0
    acted = [False] * n
    folded = [False] * n
    raise_size = 0.0
    vpip = [False] * n
    pfr = [False] * n
    for a in actions:
        t = a.split()
        if not t:
            return "an empty action"
        if t[0] == "d":
            if t[1] == "db":
                break  # preflop is over
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
        k = ("f", "cc", "cbr").index(act)
        blind = i < 2
        first = not acted[i]
        if raises == 0:
            if not blind and not limpers:
                adds[i].append((E1 + k, 1.0))
            elif not blind:
                adds[i].append((E2 + k, 1.0))
            elif i == 0 and limpers:
                adds[i].append((E6_SB + k, 1.0))
            elif i == 1 and limpers and act != "f":
                adds[i].append((E6_BB + (k == 2), 1.0))
        elif raises == 1:
            if i in limpers:
                b = bucket(raise_size - limpers_at_raise, ISO_EDGES)
                adds[i].append((E3 + 3 * b + k, 1.0))
                adds[i].append((E3 + 12 + b, raise_size - limpers_at_raise))
            elif first and limpers_at_raise == 0 and blind:
                base = E4_SB if i == 0 else E4_BB
                b = bucket(raise_size, OPEN_EDGES)
                adds[i].append((base + 3 * b + k, 1.0))
                adds[i].append((base + 12 + b, raise_size))
            elif first and limpers_at_raise == 0:
                adds[i].append((E5 + k, 1.0))
        if first and (act == "cbr" or (act == "cc" and contrib[i] < level)):
            vpip[i] = True
        acted[i] = True
        if act == "f":
            folded[i] = True
        elif act == "cc":
            if raises == 0 and not blind:
                limpers.append(i)
            contrib[i] = level
        else:
            try:
                amount = float(t[2])
            except (IndexError, ValueError):
                return f"a bet without an amount {a!r}"
            pfr[i] = True
            if raises == 0:
                limpers_at_raise = len(limpers)
                raise_size = amount / bb
            raises += 1
            contrib[i], level = amount, amount
    for i in range(n):
        if vpip[i]:
            adds[i].append((VPIP, 1.0))
        if pfr[i]:
            adds[i].append((PFR, 1.0))
    return players, adds


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


def folder_job(args: tuple[str, list[str]]) -> tuple[str, dict, Counter]:
    """One site-and-stake folder: (folder, per-player counters, hands that did not count)."""
    folder, members = args
    per_player: dict[str, array] = {}
    skipped: Counter = Counter()
    site = STAKE.match(folder).group("site")
    with zipfile.ZipFile(ZIP) as z:
        for name in members:
            text = z.read(name).decode("utf-8", "replace")
            for block in blocks(text):
                result = parse_hand(block)
                if isinstance(result, str):
                    skipped[result] += 1
                    continue
                players, adds = result
                for p, items in zip(players, adds, strict=True):
                    key = f"{site}:{p}"
                    c = per_player.get(key)
                    if c is None:
                        c = per_player[key] = array("d", bytes(8 * WIDTH))
                    for idx, v in items:
                        c[idx] += v
    return folder, per_player, skipped


def verify() -> None:
    if ZIP.stat().st_size != SIZE:
        sys.exit("zip size does not match DECISIONS 39")
    sha = hashlib.sha256()
    with open(ZIP, "rb") as f:
        while chunk := f.read(1 << 24):
            sha.update(chunk)
    if sha.hexdigest() != SHA256:
        sys.exit("zip SHA-256 does not match DECISIONS 39")


def bucket_of(c: array) -> str | None:
    vpip, pfr = c[VPIP] / c[HANDS], c[PFR] / c[HANDS]
    if vpip < 0.20:
        return "tight"
    if vpip < 0.35:
        return "regular"
    return "loose-passive" if pfr < vpip / 2 else None


FALLBACK = {
    "tight": dict(
        open_raise=0.12, limp=0.10, iso_fold=0.50, iso_reraise=0.02, iso_slope=0.06,
        behind_3bet=0.04, behind_call=0.04, sb_3bet=0.04, sb_call=0.05, bb_3bet=0.04,
        bb_call=0.25, behind_slope=0.04, limp_raise=0.08, overlimp=0.05, sb_limp_raise=0.08,
        sb_complete=0.20, bb_limp_raise=0.08,
    ),
    "regular": dict(
        open_raise=0.13, limp=0.20, iso_fold=0.40, iso_reraise=0.04, iso_slope=0.04,
        behind_3bet=0.05, behind_call=0.07, sb_3bet=0.05, sb_call=0.08, bb_3bet=0.05,
        bb_call=0.35, behind_slope=0.04, limp_raise=0.10, overlimp=0.10, sb_limp_raise=0.10,
        sb_complete=0.35, bb_limp_raise=0.10,
    ),
    "loose-passive": dict(
        open_raise=0.07, limp=0.40, iso_fold=0.25, iso_reraise=0.03, iso_slope=0.02,
        behind_3bet=0.02, behind_call=0.15, sb_3bet=0.02, sb_call=0.20, bb_3bet=0.02,
        bb_call=0.50, behind_slope=0.02, limp_raise=0.04, overlimp=0.30, sb_limp_raise=0.04,
        sb_complete=0.60, bb_limp_raise=0.04,
    ),
}


def share(c: list[float], base: int, k: int, width: int = 3) -> tuple[float | None, int]:
    """The share of outcome k among `width` outcomes at `base`, and the chances."""
    total = sum(c[base : base + width])
    return (c[base + k] / total if total else None), int(total)


def pooled(c: list[float], base: int, k: int) -> tuple[float | None, int]:
    """Outcome k's share over the 4 size buckets at `base`."""
    total = sum(c[base : base + 12])
    hits = sum(c[base + 3 * b + k] for b in range(4))
    return (hits / total if total else None), int(total)


def slope(c: list[float], base: int) -> tuple[float | None, list[tuple[float, float, int]]]:
    """Chance-weighted least-squares slope of the fold share on each bucket's mean size."""
    points = []
    for b in range(4):
        n = sum(c[base + 3 * b : base + 3 * b + 3])
        if n:
            points.append((c[base + 12 + b] / n, c[base + 3 * b] / n, int(n)))
    usable = [p for p in points if p[2] >= MIN_CHANCES]
    if len(usable) < 3:
        return None, points
    w = sum(n for _, _, n in usable)
    mx = sum(x * n for x, _, n in usable) / w
    my = sum(y * n for _, y, n in usable) / w
    sxx = sum(n * (x - mx) ** 2 for x, _, n in usable)
    sxy = sum(n * (x - mx) * (y - my) for x, y, n in usable)
    return sxy / sxx, points


def rates(c: list[float]) -> tuple[dict, dict, dict, dict]:
    """(rates, chances, sources, size curves) for one bucket's summed counters."""
    raw = {
        "open_raise": share(c, E1, 2),
        "limp": share(c, E1, 1),
        "iso_fold": share(c, E3 + 3 * ISO_REF, 0),
        "iso_reraise": pooled(c, E3, 2),
        "behind_3bet": share(c, E5, 2),
        "behind_call": share(c, E5, 1),
        "sb_3bet": pooled(c, E4_SB, 2),
        "sb_call": share(c, E4_SB + 3 * OPEN_REF, 1),
        "bb_3bet": pooled(c, E4_BB, 2),
        "bb_call": share(c, E4_BB + 3 * OPEN_REF, 1),
        "limp_raise": share(c, E2, 2),
        "overlimp": share(c, E2, 1),
        "sb_limp_raise": share(c, E6_SB, 2),
        "sb_complete": share(c, E6_SB, 1),
        "bb_limp_raise": share(c, E6_BB, 1, width=2),
    }
    iso_slope, iso_points = slope(c, E3)
    open_slope, open_points = slope(c, E4_BB)
    out, chances, source = {}, {}, {}
    for key, (value, n) in raw.items():
        out[key], chances[key] = value, n
    out["iso_slope"], chances["iso_slope"] = iso_slope, sum(p[2] for p in iso_points)
    out["behind_slope"], chances["behind_slope"] = open_slope, sum(p[2] for p in open_points)
    for key in out:
        ok = out[key] is not None and (
            key.endswith("slope") or chances[key] >= MIN_CHANCES
        )
        source[key] = "fitted" if ok else "assumed"
    curves = {"iso": iso_points, "bb_open": open_points}
    return out, chances, source, curves


def main() -> int:
    start = time.perf_counter()
    verify()
    print(f"zip verified, SHA-256 {SHA256}", flush=True)
    by_folder: dict[str, list[str]] = defaultdict(list)
    with zipfile.ZipFile(ZIP) as z:
        for name in z.namelist():
            if name.startswith(PREFIX) and name.endswith(".phhs"):
                by_folder[STAKE.match(name).group(0)].append(name)
    jobs = sorted(by_folder.items(), key=lambda kv: -len(kv[1]))
    players: dict[str, array] = {}
    skipped: Counter = Counter()
    with ProcessPoolExecutor(max_workers=12) as pool:
        for folder, per_player, skips in pool.map(folder_job, jobs):
            for p, c in per_player.items():
                total = players.get(p)
                if total is None:
                    players[p] = c
                else:
                    for k in range(WIDTH):
                        total[k] += c[k]
            skipped += skips
            print(f"  {folder}: done", flush=True)

    sums = {b: [0.0] * WIDTH for b in FALLBACK}
    members: Counter = Counter()
    left_out = 0
    for c in players.values():
        if c[HANDS] < MIN_HANDS:
            continue
        b = bucket_of(c)
        if b is None:
            left_out += 1
            continue
        members[b] += 1
        s = sums[b]
        for k in range(WIDTH):
            s[k] += c[k]

    profiles = {}
    for b, c in sums.items():
        fitted, chances, source, curves = rates(c)
        values = {
            k: (fitted[k] if source[k] == "fitted" else FALLBACK[b][k]) for k in FALLBACK[b]
        }
        profiles[b] = {
            "rates": values,
            "source": source,
            "chances": chances,
            "curves": curves,
            "players": members[b],
            "player_hands": int(c[HANDS]),
            "vpip": c[VPIP] / c[HANDS] if c[HANDS] else None,
            "pfr": c[PFR] / c[HANDS] if c[HANDS] else None,
        }

    payload = {
        "decision": 53,
        "source": "PHH dataset (Juho Kim, Zenodo, DOI 10.5281/zenodo.17136841, CC BY 4.0), "
        "data/handhq/, 3 to 6 players, no antes",
        "zip_sha256": SHA256,
        "min_hands": MIN_HANDS,
        "min_chances": MIN_CHANCES,
        "players_seen": len(players),
        "left_out_loose_aggressive": left_out,
        "hands_skipped": dict(skipped.most_common()),
        "profiles": profiles,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8", newline="\n")

    def pct(x):
        return "-" if x is None else f"{100 * x:.1f}%"

    lines = [
        "# Six-max profiles, fitted to the PHH hands (DECISIONS 53)",
        "",
        "**Read this first:** these are 2009 real-money online players at 25NL and up, "
        "3 to 6 handed, with no antes. They are priors for `showdown sixmax`, not "
        "measurements of anyone Ian plays.",
        "",
        'Source: "A Dataset of Poker Hand Histories", Juho Kim, Zenodo, '
        "DOI 10.5281/zenodo.17136841, CC BY 4.0, its `data/handhq/` folder. Nothing from "
        "it is committed except these aggregates.",
        "",
        f"Zip SHA-256: `{SHA256}`. Spike: `spikes/2026-11-22-phh-sixmax-profiles.py`. "
        f"Players seen: {len(players):,}. With at least {MIN_HANDS} hands and "
        f"loose-aggressive, left out: {left_out:,}.",
        "",
        "Hands that did not count: "
        + (", ".join(f"{k}: {v:,}" for k, v in skipped.most_common()) or "none")
        + ".",
        "",
        "## Buckets",
        "",
        "| Bucket | Players | Player-hands | VPIP | PFR |",
        "|---|---|---|---|---|",
    ]
    for b, p in profiles.items():
        lines.append(
            f"| {b} | {p['players']:,} | {p['player_hands']:,} | {pct(p['vpip'])} | "
            f"{pct(p['pfr'])} |"
        )
    lines += [
        "",
        "## The engine's rates",
        "",
        f"Each rate's chances are in brackets. \"assumed\" means fewer than {MIN_CHANCES:,} "
        "chances (or fewer than three size buckets with that many, for a slope), so the "
        "hand-picked value from DECISIONS 53 is used.",
        "",
        "| Rate | " + " | ".join(profiles) + " |",
        "|---|" + "---|" * len(profiles),
    ]
    for key in FALLBACK["tight"]:
        cells = []
        for p in profiles.values():
            v, n, src = p["rates"][key], p["chances"][key], p["source"][key]
            text = f"{v:+.3f}/bb" if key.endswith("slope") else pct(v)
            cells.append(f"{text} ({n:,}){' assumed' if src == 'assumed' else ''}")
        lines.append(f"| {key} | " + " | ".join(cells) + " |")
    lines += ["", "## Fold share by size", ""]
    for b, p in profiles.items():
        for name, label in (("iso", "limper vs an iso, m in bb"), ("bb_open", "BB vs an open, bb")):
            pts = ", ".join(f"{x:.2f}: {pct(y)} ({n:,})" for x, y, n in p["curves"][name])
            lines.append(f"- {b}, {label}: {pts or 'none'}")
    lines += [
        "",
        "## Definitions",
        "",
        "- **First in:** not a blind, everyone before folded. Limp = call the big blind.",
        "- **Facing limpers:** not a blind, one or more limpers and no raise.",
        "- **A limper facing one raise:** its next action after limping, with exactly one "
        "raise in. m = the raise-to minus the limpers before the raiser, in bb.",
        "- **A blind facing one open:** no limpers, exactly one raise, its first action.",
        "- **Players behind:** not a blind, facing one raise and no limpers, first action.",
        "- **Blinds facing limpers:** the SB folds, completes or raises; the BB checks or "
        "raises.",
        "",
        f"Runtime: {time.perf_counter() - start:.0f} s.",
        "",
    ]
    OUT_DOC.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
