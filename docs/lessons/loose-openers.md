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

| Hand | vs LAG: call / 3-bet to 7.5 / jam | vs Maniac: call / 3-bet to 7.5 |
|---|---|---|
| AJo | +0.15 / +1.42 / −0.66 | +0.20 / +1.52 |
| 99 | +1.08 / +1.36 / −1.60 | +1.18 / +1.51 |
| KQo | −0.19 / +0.68 / −0.57 | −0.06 / +0.65 |
| A5s | −0.28 / +0.66 / −1.34 | −0.17 / +0.70 |

These are at DECISIONS 64's model: a flat call share across 3-bet sizes, and R 0.85 for a
called 3-bet in position. The smaller 3-bet is now the better size.

## Limits

The engine still leans towards 3-betting facing an open. Trash 3-bets went from "clear" to
"close" with the fix, but Gate Z2 found too few stable hands to pass its chart bar
([`sixmax-preflop.md`](../sixmax-preflop.md)). Trust the value 3-bets above; treat a close
3-bet with a weak hand as a fold.

## Links

None yet. External links are added only after Ian approves each one.
