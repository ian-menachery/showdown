# How often real players make the common moves (DECISIONS 39)

**Read this first:** these are 2009 real-money online hands, mostly 6-max, from the PHH dataset. Heads-up play-money games with friends will differ. They are candidate starting points for Phase 12's opponent model, not facts about anyone Ian plays.

Source: "A Dataset of Poker Hand Histories", Juho Kim, Zenodo, DOI 10.5281/zenodo.17136841, CC BY 4.0. The online hands are its `data/handhq/` folder (HandHQ, July 2009, obfuscated player names). Nothing from it is committed.

Zip SHA-256: `65d566e7a3387b4c3ec28213b5416a8a36a4f4f1cf822771b77f5232fbba3281`. Spike: `spikes/2026-11-15-phh-leaks.py`.

Counted: 116,861,965 player-hands. Hands that did not count: 0 (none).

## By table size

| Table | Player-hands | VPIP | PFR | 3-bet | Flop c-bet | Fold to flop c-bet |
|---|---|---|---|---|---|---|
| heads-up | 6,109,392 | 49.4% | 33.8% | 14.0% (1,813,802) | 63.2% (737,487) | 45.3% (465,745) |
| 3-6 | 72,497,321 | 27.1% | 15.2% | 5.8% (25,145,691) | 65.0% (3,815,242) | 50.6% (2,828,399) |
| 7+ | 38,255,252 | 20.2% | 8.8% | 3.3% (11,671,342) | 67.9% (1,170,576) | 54.2% (975,215) |

Rates in brackets give the number of chances.

## By stake, 3-6 handed

| Stake | Player-hands | VPIP | PFR | 3-bet | Flop c-bet | Fold to flop c-bet |
|---|---|---|---|---|---|---|
| 25NL | 18,652,172 | 28.1% | 12.7% | 4.2% | 67.8% | 52.2% |
| 50NL | 4,629,726 | 28.6% | 13.3% | 4.5% | 66.3% | 52.6% |
| 100NL | 7,592,802 | 26.2% | 14.9% | 5.5% | 62.2% | 51.1% |
| 200NL | 10,511,945 | 26.1% | 15.5% | 6.0% | 63.1% | 51.0% |
| 400NL | 15,714,294 | 26.9% | 16.6% | 6.4% | 64.7% | 49.6% |
| 600NL | 6,984,003 | 27.3% | 16.9% | 6.6% | 64.6% | 49.0% |
| 1000NL | 8,412,379 | 26.4% | 17.7% | 7.3% | 64.0% | 48.0% |

## Across players with at least 500 hands

34,301 players (of 280,389 seen).

| | 25th percentile | Median | 75th percentile |
|---|---|---|---|
| VPIP | 18.8% | 25.4% | 36.5% |
| PFR | 8.2% | 12.8% | 17.6% |

VPIP at least 40% (loose): 19.6% of these players. VPIP at most 15% (tight): 13.0%.

## Definitions (DECISIONS 39, amended)

- **VPIP:** the first voluntary preflop action is a call with chips owed, or a raise. The big blind checking is not VPIP.
- **PFR:** raises preflop.
- **3-bet:** facing exactly one preflop raise, raises.
- **Flop c-bet:** the last preflop raiser sees the flop and acts before anyone bets; it bets.
- **Fold to flop c-bet:** facing that bet, before any raise of it, the first action is a fold.

Runtime: 790 s.
