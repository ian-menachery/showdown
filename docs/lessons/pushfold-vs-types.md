# Push/fold against player types

Tournament-style, no ICM. Against a tight caller, jam wider. Against a tight jammer, call
tighter. Against a maniac, call wider and jam almost anything.

## The idea

At 10 bb or less, the SB's choice is jam or fold, and the BB's is call or fold. Nash is the
answer that can't be exploited. Against a known type, the best response moves away from it:
- a caller who folds too much makes every jam profitable;
- a jammer who jams only strong hands makes your calls lose.

## Rule of thumb

- SB against a Nit BB (calls about 20% of hands at 10 bb): jam everything Nash jams, and more.
- BB against a Nit SB (jams about 39%): fold K5o, Q8s and T9s, which Nash would call. Keep
  A2o.
- BB against a Maniac (jams everything): call almost any two.

## The engine's numbers

10 bb, EV in bb per hand (fold is −0.5 for the SB and −1 for the BB):

| Hand | SB jam vs Nit / standard / Maniac | BB call vs Nit / standard / Maniac |
|---|---|---|
| K5o | +0.13 / −0.20 / +0.33 | −2.19 / −0.86 / +0.66 |
| Q8s | +0.25 / −0.07 / +0.75 | −1.83 / −0.44 / +1.20 |
| A2o | +0.39 / +0.32 / +0.69 | −0.75 / +0.08 / +0.99 |
| T9s | +0.34 / −0.03 / +0.31 | −1.79 / −1.04 / +0.81 |

## Limits

A type's width is Nash's width times that type's 2009 ratio, the top hands by equity. Real
players don't jam by a strict equity order. There's no ICM: in a real tournament, survival
is worth more than chips near the money.

## Links

None yet. External links are added only after Ian approves each one.
