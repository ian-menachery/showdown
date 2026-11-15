"""pokerkit's Monte Carlo equity as a reproducible test oracle (DECISIONS 28).

pokerkit samples with the global `random` module from a deck whose order
depends on Python's per-process string hashing. So `random.seed` alone does not
make its result reproducible: the same seed gives a different sample in every
process. This helper runs pokerkit in a subprocess with `PYTHONHASHSEED=0`, a
value fixed before any result was seen, and seeds `random` per case. The
oracle is then one fixed draw, and a 3 SE comparison against it is
reproducible run to run.
"""

import json
import os
import subprocess
import sys

HASH_SEED = "0"

_SCRIPT = r"""
import json, random, sys, warnings
from pokerkit import Card, Deck, StandardHighHand, calculate_equities, parse_range
warnings.simplefilter("ignore")
out = []
for ranges, board, samples, seed in json.loads(sys.stdin.read()):
    random.seed(seed)
    out.append(list(calculate_equities(
        tuple(parse_range(r) for r in ranges),
        tuple(Card.parse(board)) if board else (),
        2, 5, Deck.STANDARD, (StandardHighHand,), sample_count=samples,
    )))
print(json.dumps(out))
"""


def equities(cases: list[tuple[tuple[str, ...], str, int, int]]) -> list[list[float]]:
    """pokerkit's `calculate_equities` for each (ranges, board, samples, seed) case."""
    env = {**os.environ, "PYTHONHASHSEED": HASH_SEED}
    result = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        input=json.dumps(cases),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)
