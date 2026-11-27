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
| CO vs Weak-tight rec: best | fold | fold | fold | fold |
| CO vs Weak-tight rec: call / 3-bet to 7.5 | −0.92 / −0.54 | −0.99 / −0.30 | −0.44 / −0.25 | −1.56 / −1.97 |
| CO vs Nit: call / 3-bet to 7.5 | −0.54 / +0.05 | −0.79 / +0.48 | −0.25 / +0.59 | −1.42 / −0.71 |
| BB vs Weak-tight rec: call | −0.08 | −0.13 | +0.37 (best) | −0.64 |

These are at DECISIONS 64's model (a flat call share, R 0.85 for a called 3-bet in
position). From the CO, folding beats calling and 3-betting against a Weak-tight rec's UTG
open with all four hands.

## Limits

The engine still leans towards 3-betting facing an open. Against a Nit it 3-bets AJo, KQo
and 99 from the CO by small margins, and 72o in the BB is a close +0.02. Gate Z2 found too
few stable hands to pass its chart bar ([`sixmax-preflop.md`](../sixmax-preflop.md)). Where
it says 3-bet a weak hand against a tight opener, folding is the safer answer.

## Links

None yet. External links are added only after Ian approves each one.
