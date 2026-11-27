# Steal from tight blinds

When the blinds fold a lot, a small open from late position wins the pot often enough that
almost any two cards profit. When they defend, steal only hands that play well when called.

## The idea

An unopened steal risks the open to win 1.5 bb (plus antes). Its EV is mostly fold equity:
how often both blinds fold. Nits and Weak-tight recs fold far more than Calling stations,
so the same hand can be a clear open against one table and a fold against the other.

## Rule of thumb

- Against tight blinds, open wide from the button with the small size (2.5 bb).
- Against sticky blinds, tighten up. Keep hands with high cards (K7o) and drop weak suited
  ones (Q5s, 93s).
- An open-limp is never better than one of fold or open here.

## The engine's numbers

BTN, unopened, no ante (EV in bb, against folding):

| Hand | Nit table | Calling-station table |
|---|---|---|
| K7o | open to 2.5 +0.39 (clear) | open to 4 +0.15 (close) |
| Q5s | open to 2.5 +0.35 (clear) | fold; open −0.05 (close) |
| J8o | open to 2.5 +0.34 (clear) | fold; open −0.09 (close) |
| 93s | open to 2.5 +0.28 (close) | fold; open −0.51 (clear) |

## Limits

Table types scale standard's blind defence by the 2009 groups' ratios
([`sixmax-types.md`](../sixmax-types.md)). Real blinds vary from these groups.

## Links

None yet. External links are added only after Ian approves each one.
