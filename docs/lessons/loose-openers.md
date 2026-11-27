# Play back at loose openers

A loose opener's range is wide and weak. 3-bet your good hands for value instead of
flatting, and defend more than you would against a tight opener.

## The idea

Against a LAG or a Maniac, hands like AJo, KQo and 99 are well ahead of the opening range.
A 3-bet builds the pot while you're ahead and takes the initiative. A flat call lets the
blinds in and gives up the betting lead.

## Rule of thumb

- Against a wide opener in late position, 3-bet AJo+, KQo and medium pairs, mostly to 3×.
- Flat a pair like 99 only when you want to keep the pot small.
- Don't jam 100 bb over an open. It only gets called by better hands.

## The engine's numbers

BTN against a CO open to 2.5, standard players behind (EV in bb, against folding):

| Hand | vs LAG: call / 3-bet to 7.5 / jam | vs Maniac: call / 3-bet to 10 |
|---|---|---|
| AJo | +0.15 / +1.94 / −0.66 | +0.20 / +2.28 |
| 99 | +1.08 / +1.94 / −1.60 | +1.18 / +2.30 |
| KQo | −0.19 / +1.11 / −0.57 | −0.06 / +1.24 |
| A5s | −0.28 / +1.05 / −1.34 | −0.17 / +1.17 |

## Limits

**Gate Z failed on its chart bar.** Facing an open, the engine overrates 3-bet bluffs: it
3-bets almost every hand, because the opener folds 55% to a 3× 3-bet and R 1.00 treats any
hand alike ([`sixmax-preflop.md`](../sixmax-preflop.md)). Trust the value 3-bets above, not
3-bets with trash.

## Links

None yet. External links are added only after Ian approves each one.
