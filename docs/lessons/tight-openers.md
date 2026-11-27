# Respect tight openers

A Nit's or a Weak-tight rec's early open is strong. Hands that are fine against a wide range
are dominated here. Fold or 3-bet the hands that beat its range, and fold the rest.

## The idea

When a tight player opens UTG, its range is mostly pairs and big aces. Calling with AJo or
KQo out of position wins small pots and loses big ones. A weak-tight opener folds a lot to a
3-bet but rarely pays off, so 3-bets are thin either way.

## Rule of thumb

- From the CO against a tight UTG open, fold the trash; never flat AJo or KQo.
- In the BB you're getting a price, so call 99 against a weak-tight opener. Against a Nit,
  calls with offsuit broadways are marginal at best.

## The engine's numbers

Against a UTG open to 2.5, standard players behind (EV in bb, against folding):

| Spot | AJo | KQo | 99 | 72o |
|---|---|---|---|---|
| CO vs Nit: call | −0.54 | −0.79 | −0.25 | −1.42 |
| CO vs Weak-tight rec: call | −0.92 | −0.99 | −0.44 | −1.56 |
| BB vs Weak-tight rec: call | −0.08 | −0.13 | +0.37 (best) | −0.64 |

The engine's 3-bets in these spots are small positives at best (KQo against the
Weak-tight rec: +0.27 from the CO). Read the limit below.

## Limits

**Gate Z failed on its chart bar:** the engine 3-bets too much facing an open, even 72o in
the BB against a Nit (+0.04, close). Where it says 3-bet a weak hand against a tight opener,
folding is the safer answer ([`sixmax-preflop.md`](../sixmax-preflop.md)).

## Links

None yet. External links are added only after Ian approves each one.
