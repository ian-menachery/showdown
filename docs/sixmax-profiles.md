# Six-max profiles, fitted to the PHH hands (DECISIONS 53)

**Read this first:** these are 2009 real-money online players at 25NL and up, 3 to 6 handed, with no antes. They are priors for `showdown sixmax`, not measurements of anyone Ian plays.

Source: "A Dataset of Poker Hand Histories", Juho Kim, Zenodo, DOI 10.5281/zenodo.17136841, CC BY 4.0, its `data/handhq/` folder. Nothing from it is committed except these aggregates.

Zip SHA-256: `65d566e7a3387b4c3ec28213b5416a8a36a4f4f1cf822771b77f5232fbba3281`. Spike: `spikes/2026-11-22-phh-sixmax-profiles.py`. Players seen: 221,427. With at least 500 hands and loose-aggressive, left out: 1,143.

Hands that did not count: not 3 to 6 players: 7,672,269, not one small and one big blind: 309,322, antes: 96,053.

## Buckets

| Bucket | Players | Player-hands | VPIP | PFR |
|---|---|---|---|---|
| tight | 4,517 | 18,935,767 | 17.4% | 13.5% |
| regular | 10,282 | 32,083,403 | 24.5% | 16.9% |
| loose-passive | 3,805 | 4,028,137 | 45.1% | 12.5% |

## The engine's rates

Each rate's chances are in brackets. "assumed" means fewer than 1,000 chances (or fewer than three size buckets with that many, for a slope), so the hand-picked value from DECISIONS 53 is used.

| Rate | tight | regular | loose-passive |
|---|---|---|---|
| open_raise | 18.8% (8,538,471) | 24.4% (14,511,809) | 17.5% (1,829,963) |
| limp | 0.8% (8,538,471) | 2.9% (14,511,809) | 30.7% (1,829,963) |
| iso_fold | 54.0% (12,014) | 47.5% (64,960) | 39.2% (86,868) |
| iso_reraise | 3.9% (35,091) | 4.1% (182,096) | 3.5% (227,378) |
| iso_slope | +0.041/bb (35,091) | +0.038/bb (182,096) | +0.037/bb (227,378) |
| behind_3bet | 4.5% (2,099,356) | 5.4% (3,601,837) | 3.6% (426,563) |
| behind_call | 7.3% (2,099,356) | 12.1% (3,601,837) | 29.8% (426,563) |
| sb_3bet | 6.3% (1,689,026) | 7.0% (3,120,900) | 4.3% (376,646) |
| sb_call | 5.4% (757,745) | 10.1% (1,512,122) | 36.7% (175,465) |
| bb_3bet | 6.9% (1,906,234) | 7.5% (3,498,684) | 4.9% (428,774) |
| bb_call | 9.7% (862,402) | 17.3% (1,698,240) | 49.2% (199,892) |
| behind_slope | +0.035/bb (1,906,234) | +0.049/bb (3,498,684) | +0.088/bb (428,774) |
| limp_raise | 14.7% (1,010,543) | 19.4% (1,317,088) | 14.2% (179,563) |
| overlimp | 4.5% (1,010,543) | 8.4% (1,317,088) | 36.3% (179,563) |
| sb_limp_raise | 9.4% (545,621) | 11.8% (738,047) | 13.7% (103,461) |
| sb_complete | 20.3% (545,621) | 32.7% (738,047) | 63.7% (103,461) |
| bb_limp_raise | 9.0% (481,618) | 11.5% (646,917) | 14.0% (90,310) |

## Fold share by size

- tight, limper vs an iso, m in bb: 2.25: 31.7% (18,637), 3.88: 54.0% (12,014), 4.96: 68.9% (2,379), 16.20: 84.9% (2,061)
- tight, BB vs an open, bb: 2.11: 72.4% (339,883), 3.00: 82.8% (862,402), 3.50: 86.1% (276,621), 5.46: 87.3% (427,328)
- regular, limper vs an iso, m in bb: 2.36: 25.2% (96,695), 3.83: 47.5% (64,960), 4.93: 62.0% (11,044), 17.47: 79.7% (9,397)
- regular, BB vs an open, bb: 2.16: 61.2% (671,112), 3.00: 74.6% (1,698,240), 3.49: 79.1% (601,064), 5.48: 80.5% (528,268)
- loose-passive, limper vs an iso, m in bb: 2.43: 19.4% (115,498), 3.83: 39.2% (86,868), 4.92: 53.0% (14,643), 17.98: 74.1% (10,369)
- loose-passive, BB vs an open, bb: 2.15: 28.0% (68,426), 3.00: 45.7% (199,892), 3.49: 53.1% (72,063), 5.34: 61.0% (88,393)

## Definitions

- **First in:** not a blind, everyone before folded. Limp = call the big blind.
- **Facing limpers:** not a blind, one or more limpers and no raise.
- **A limper facing one raise:** its next action after limping, with exactly one raise in. m = the raise-to minus the limpers before the raiser, in bb.
- **A blind facing one open:** no limpers, exactly one raise, its first action.
- **Players behind:** not a blind, facing one raise and no limpers, first action.
- **Blinds facing limpers:** the SB folds, completes or raises; the BB checks or raises.

Runtime: 803 s.
