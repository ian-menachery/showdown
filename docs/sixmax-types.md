# Six-max player types, fitted to the PHH hands (DECISIONS 60)

**Read this first:** these are 2009 real-money online players at 25NL and up, 3 to 6 handed, with no antes, grouped by their own VPIP and PFR. They are priors for the trainer's opponents, not measurements of anyone Ian plays.

Source: "A Dataset of Poker Hand Histories", Juho Kim, Zenodo, DOI 10.5281/zenodo.17136841, CC BY 4.0, its `data/handhq/` folder. Nothing from it is committed except these aggregates.

Zip SHA-256: `65d566e7a3387b4c3ec28213b5416a8a36a4f4f1cf822771b77f5232fbba3281`. Spike: `spikes/2026-11-27-phh-sixmax-types.py`. Players seen: 221,427; with at least 500 hands: 19,747.

## Groups and trait cards

Aggressive means PFR at least half of VPIP. Limp is limp first in; fold to iso is a limper facing a 4+k iso; 3-bet is a non-blind player facing an open; BB defence is call or 3-bet facing a 2.75 to 3.25 bb open.

| Type | Rule | Players | VPIP | PFR | Limp | Fold to iso | 3-bet | BB defence |
|---|---|---|---|---|---|---|---|---|
| Nit | aggressive, VPIP < 16% | 1,095 | 14.2% | 11.0% | 0.6% | 51.0% | 3.8% | 14.2% |
| TAG | aggressive, VPIP 16-28% | 8,535 | 21.3% | 16.6% | 0.5% | 50.5% | 5.5% | 21.1% |
| LAG | aggressive, VPIP 28-40% | 2,042 | 31.9% | 21.7% | 2.5% | 46.8% | 6.5% | 35.6% |
| Maniac | aggressive, VPIP 40%+ | 627 | 46.8% | 27.7% | 7.3% | 41.2% | 6.6% | 56.1% |
| Weak-tight rec | passive, VPIP < 24% | 985 | 19.7% | 7.0% | 10.3% | 53.5% | 2.2% | 22.5% |
| Calling station | passive, VPIP 24%+ | 6,463 | 37.6% | 11.2% | 23.9% | 41.5% | 3.2% | 45.3% |
| All players | every player above | 19,747 | 24.1% | 15.7% | 4.3% | 43.6% | 5.0% | 25.7% |

## The engine's rates

Chances in brackets. "pooled" means fewer than 1,000 chances (or fewer than three size buckets with that many, for a slope), so the "all" group's value is used.

| Rate | Nit | TAG | LAG | Maniac | Weak-tight rec | Calling station | All players |
|---|---|---|---|---|---|---|---|
| open_raise | 15.0% (1,674,130) | 23.7% (17,257,461) | 32.4% (1,902,865) | 42.1% (357,161) | 9.9% (892,771) | 15.8% (3,517,747) | 22.5% (25,602,135) |
| limp | 0.6% (1,674,130) | 0.5% (17,257,461) | 2.5% (1,902,865) | 7.3% (357,161) | 10.3% (892,771) | 23.9% (3,517,747) | 4.3% (25,602,135) |
| iso_fold | 51.0% (1,978) | 50.5% (16,100) | 46.8% (7,577) | 41.2% (4,258) | 53.5% (12,976) | 41.5% (127,853) | 43.6% (170,742) |
| iso_reraise | 3.4% (5,885) | 5.0% (47,398) | 5.5% (22,220) | 5.0% (11,564) | 3.8% (36,689) | 3.5% (339,907) | 3.8% (463,663) |
| iso_slope | +0.038/bb (5,885) pooled | +0.039/bb (47,398) | +0.038/bb (22,220) | +0.038/bb (11,564) pooled | +0.040/bb (36,689) | +0.037/bb (339,907) | +0.038/bb (463,663) |
| behind_3bet | 3.8% (392,129) | 5.5% (4,326,530) | 6.5% (457,092) | 6.6% (83,404) | 2.2% (208,839) | 3.2% (828,637) | 5.0% (6,296,631) |
| behind_call | 5.8% (392,129) | 9.6% (4,326,530) | 16.3% (457,092) | 30.7% (83,404) | 10.8% (208,839) | 23.9% (828,637) | 12.1% (6,296,631) |
| sb_3bet | 5.0% (306,700) | 7.3% (3,653,731) | 8.0% (424,450) | 7.6% (78,772) | 2.8% (167,297) | 3.8% (715,550) | 6.6% (5,346,500) |
| sb_call | 4.8% (125,026) | 6.9% (1,749,388) | 15.7% (213,950) | 35.8% (39,514) | 13.2% (69,635) | 29.6% (328,371) | 11.1% (2,525,884) |
| bb_3bet | 5.5% (346,070) | 7.9% (4,101,061) | 8.5% (477,737) | 8.2% (89,255) | 2.9% (189,596) | 4.3% (811,177) | 7.1% (6,014,896) |
| bb_call | 8.1% (142,590) | 12.7% (1,970,915) | 26.4% (238,872) | 47.8% (44,213) | 19.3% (80,461) | 40.8% (373,462) | 18.0% (2,850,513) |
| behind_slope | +0.034/bb (346,070) | +0.039/bb (4,101,061) | +0.070/bb (477,737) | +0.077/bb (89,255) | +0.069/bb (189,596) | +0.086/bb (811,177) | +0.049/bb (6,014,896) |
| limp_raise | 11.9% (242,692) | 19.2% (1,658,136) | 24.2% (148,217) | 30.4% (25,607) | 7.1% (120,344) | 12.1% (365,778) | 17.3% (2,560,774) |
| overlimp | 3.9% (242,692) | 4.5% (1,658,136) | 10.9% (148,217) | 21.6% (25,607) | 14.6% (120,344) | 29.4% (365,778) | 9.0% (2,560,774) |
| sb_limp_raise | 8.4% (131,609) | 11.3% (910,597) | 15.8% (88,098) | 26.9% (15,622) | 6.0% (66,895) | 11.3% (206,782) | 11.2% (1,419,603) |
| sb_complete | 15.9% (131,609) | 24.4% (910,597) | 39.9% (88,098) | 49.8% (15,622) | 39.1% (66,895) | 58.6% (206,782) | 30.5% (1,419,603) |
| bb_limp_raise | 7.8% (117,039) | 11.1% (797,320) | 14.3% (77,311) | 24.3% (13,942) | 5.9% (59,825) | 11.4% (182,040) | 10.9% (1,247,477) |
| opener_fold | 55.7% (37,704) | 58.7% (781,855) | 50.9% (124,211) | 40.9% (31,628) | 42.8% (12,380) | 35.9% (96,159) | 55.0% (1,083,937) |
| opener_call | 31.7% (37,704) | 29.7% (781,855) | 40.3% (124,211) | 52.9% (31,628) | 47.5% (12,380) | 56.0% (96,159) | 34.2% (1,083,937) |
| opener_4bet | 12.5% (37,704) | 11.6% (781,855) | 8.8% (124,211) | 6.3% (31,628) | 9.7% (12,380) | 8.1% (96,159) | 10.8% (1,083,937) |

Count 7, the opener facing one 3-bet: a player whose first raise opened a pot with no limpers, at its next action with exactly two raises in.

Runtime: 572 s.
