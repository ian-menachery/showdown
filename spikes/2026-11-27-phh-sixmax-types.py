r"""Spike, 2026-11-27: the six-max player types, fitted to the PHH hands (DECISIONS 60).

The same zip, filters and counts as DECISIONS 53's spike
(`2026-11-22-phh-sixmax-profiles.py`), plus count 7: the opener facing one 3-bet. Players
with at least 500 hands are grouped into six types by their own VPIP and PFR, and an
"all" group pools every one of them, for the ratios. DECISIONS 60 fixes the groups, the
counts and the fallback before this script ran.

Writes data/sixmax_types.json and docs/sixmax-types.md, aggregates only. Run from the
repo root:

    .venv\Scripts\python -I spikes\2026-11-27-phh-sixmax-types.py

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
OUT_JSON = Path("data/sixmax_types.json")
OUT_DOC = Path("docs/sixmax-types.md")
MIN_HANDS = 500
MIN_CHANCES = 1_000
STAKE = re.compile(r"data/handhq/(?P<site>[A-Z]+)-[^_]+_[^_]+_(?P<stake>\d+)NLH_OBFU/")

ISO_EDGES = (3.5, 4.5, 5.5)  # m = raise-to minus limpers, in bb
OPEN_EDGES = (2.75, 3.25, 3.75)  # open size in bb
ISO_REF, OPEN_REF = 1, 1  # the bucket index holding the engine's reference size

# Per-player counters, one flat array of doubles (DECISIONS 53's layout, then count 7).
HANDS, VPIP, PFR = 0, 1, 2
E1 = 3  # first in: fold, limp, raise
E2 = 6  # facing limpers: fold, overlimp, raise
E3 = 9  # limper facing one raise: 4 buckets x (fold, call, re-raise), then 4 sums of m
E4_SB = 25  # SB facing one open: 4 buckets x (fold, call, 3-bet), then 4 sums of size
E4_BB = 41  # the same for the BB
E5 = 57  # non-blind facing one open: fold, call, 3-bet
E6_SB = 60  # SB facing limpers: fold, complete, raise
E6_BB = 63  # BB facing limpers: check, raise
E7 = 65  # the opener facing one 3-bet: fold, call, 4-bet
WIDTH = 68

TYPES = ("nit", "tag", "lag", "maniac", "weak-tight", "station")
NAMES = {
    "nit": "Nit",
    "tag": "TAG",
    "lag": "LAG",
    "maniac": "Maniac",
    "weak-tight": "Weak-tight rec",
    "station": "Calling station",
    "all": "All players",
}


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
    opener = -1
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
        elif raises == 2 and i == opener:
            adds[i].append((E7 + k, 1.0))
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
                if not limpers:
                    opener = i
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


def type_of(c: array) -> str:
    """DECISIONS 60's six groups, by the player's own VPIP and PFR."""
    vpip, pfr = c[VPIP] / c[HANDS], c[PFR] / c[HANDS]
    if pfr >= vpip / 2:
        if vpip < 0.16:
            return "nit"
        if vpip < 0.28:
            return "tag"
        return "lag" if vpip < 0.40 else "maniac"
    return "weak-tight" if vpip < 0.24 else "station"


ALL_FALLBACK = dict(
    # DECISIONS 53's hand-picked regular values, used only if the pooled group is thin.
    open_raise=0.13, limp=0.20, iso_fold=0.40, iso_reraise=0.04, iso_slope=0.04,
    behind_3bet=0.05, behind_call=0.07, sb_3bet=0.05, sb_call=0.08, bb_3bet=0.05,
    bb_call=0.35, behind_slope=0.04, limp_raise=0.10, overlimp=0.10, sb_limp_raise=0.10,
    sb_complete=0.35, bb_limp_raise=0.10, opener_fold=0.55, opener_call=0.33,
    opener_4bet=0.12,
)


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


def rates(c: list[float]) -> tuple[dict, dict, dict]:
    """(rates or None, chances, the trait card) for one group's summed counters."""
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
        "opener_fold": share(c, E7, 0),
        "opener_call": share(c, E7, 1),
        "opener_4bet": share(c, E7, 2),
    }
    out, chances = {}, {}
    for key, (value, n) in raw.items():
        ok = value is not None and n >= MIN_CHANCES
        out[key], chances[key] = (value if ok else None), n
    for key, base in (("iso_slope", E3), ("behind_slope", E4_BB)):
        value, points = slope(c, base)
        out[key], chances[key] = value, sum(p[2] for p in points)
    ref = E4_BB + 3 * OPEN_REF
    defend, _ = share(c, ref, 0)
    card = {
        "vpip": c[VPIP] / c[HANDS] if c[HANDS] else None,
        "pfr": c[PFR] / c[HANDS] if c[HANDS] else None,
        "limp": raw["limp"][0],
        "iso_fold": raw["iso_fold"][0],
        "three_bet": raw["behind_3bet"][0],
        "bb_defence": None if defend is None else 1.0 - defend,
    }
    return out, chances, card


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

    groups = (*TYPES, "all")
    sums = {g: [0.0] * WIDTH for g in groups}
    members: Counter = Counter()
    for c in players.values():
        if c[HANDS] < MIN_HANDS:
            continue
        for g in (type_of(c), "all"):
            members[g] += 1
            s = sums[g]
            for k in range(WIDTH):
                s[k] += c[k]

    fitted = {g: rates(sums[g]) for g in groups}
    all_rates = fitted["all"][0]
    pool_values = {k: (v if v is not None else ALL_FALLBACK[k]) for k, v in all_rates.items()}
    pool_source = {k: ("fitted" if v is not None else "assumed") for k, v in all_rates.items()}
    types = {}
    for g in groups:
        values, chances, card = fitted[g]
        if g == "all":
            rates_g, source = pool_values, pool_source
        else:
            rates_g = {k: (v if v is not None else pool_values[k]) for k, v in values.items()}
            source = {k: ("fitted" if v is not None else "pooled") for k, v in values.items()}
        types[g] = {
            "name": NAMES[g],
            "players": members[g],
            "player_hands": int(sums[g][HANDS]),
            "rates": rates_g,
            "source": source,
            "chances": chances,
            "card": card,
        }

    payload = {
        "decision": 60,
        "source": "PHH dataset (Juho Kim, Zenodo, DOI 10.5281/zenodo.17136841, CC BY 4.0), "
        "data/handhq/, 3 to 6 players, no antes",
        "zip_sha256": SHA256,
        "min_hands": MIN_HANDS,
        "min_chances": MIN_CHANCES,
        "players_seen": len(players),
        "hands_skipped": dict(skipped.most_common()),
        "types": types,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8", newline="\n")

    def pct(x):
        return "-" if x is None else f"{100 * x:.1f}%"

    lines = [
        "# Six-max player types, fitted to the PHH hands (DECISIONS 60)",
        "",
        "**Read this first:** these are 2009 real-money online players at 25NL and up, "
        "3 to 6 handed, with no antes, grouped by their own VPIP and PFR. They are priors "
        "for the trainer's opponents, not measurements of anyone Ian plays.",
        "",
        'Source: "A Dataset of Poker Hand Histories", Juho Kim, Zenodo, '
        "DOI 10.5281/zenodo.17136841, CC BY 4.0, its `data/handhq/` folder. Nothing from "
        "it is committed except these aggregates.",
        "",
        f"Zip SHA-256: `{SHA256}`. Spike: `spikes/2026-11-27-phh-sixmax-types.py`. "
        f"Players seen: {len(players):,}; with at least {MIN_HANDS} hands: "
        f"{members['all']:,}.",
        "",
        "## Groups and trait cards",
        "",
        "Aggressive means PFR at least half of VPIP. Limp is limp first in; fold to iso is "
        "a limper facing a 4+k iso; 3-bet is a non-blind player facing an open; BB defence "
        "is call or 3-bet facing a 2.75 to 3.25 bb open.",
        "",
        "| Type | Rule | Players | VPIP | PFR | Limp | Fold to iso | 3-bet | BB defence |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    rule = {
        "nit": "aggressive, VPIP < 16%",
        "tag": "aggressive, VPIP 16-28%",
        "lag": "aggressive, VPIP 28-40%",
        "maniac": "aggressive, VPIP 40%+",
        "weak-tight": "passive, VPIP < 24%",
        "station": "passive, VPIP 24%+",
        "all": "every player above",
    }
    for g, t in types.items():
        k = t["card"]
        lines.append(
            f"| {t['name']} | {rule[g]} | {t['players']:,} | {pct(k['vpip'])} | "
            f"{pct(k['pfr'])} | {pct(k['limp'])} | {pct(k['iso_fold'])} | "
            f"{pct(k['three_bet'])} | {pct(k['bb_defence'])} |"
        )
    lines += [
        "",
        "## The engine's rates",
        "",
        f"Chances in brackets. \"pooled\" means fewer than {MIN_CHANCES:,} chances (or fewer "
        "than three size buckets with that many, for a slope), so the \"all\" group's value "
        "is used.",
        "",
        "| Rate | " + " | ".join(t["name"] for t in types.values()) + " |",
        "|---|" + "---|" * len(types),
    ]
    for key in ALL_FALLBACK:
        cells = []
        for t in types.values():
            v, n, src = t["rates"][key], t["chances"][key], t["source"][key]
            text = f"{v:+.3f}/bb" if key.endswith("slope") else pct(v)
            cells.append(f"{text} ({n:,}){'' if src == 'fitted' else ' ' + src}")
        lines.append(f"| {key} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "Count 7, the opener facing one 3-bet: a player whose first raise opened a pot "
        "with no limpers, at its next action with exactly two raises in.",
        "",
        f"Runtime: {time.perf_counter() - start:.0f} s.",
        "",
    ]
    OUT_DOC.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
