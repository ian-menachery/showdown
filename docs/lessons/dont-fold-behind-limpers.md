# Don't over-fold behind limpers

Limpers put dead money in the pot. On the button, with an ante, many hands that would fold
unopened can overlimp or isolate profitably.

## The idea

Every limp and every ante makes the pot bigger before you act, so the price of joining
falls. Hands that play well in position (suited kings, suited connectors, any ace) gain
from the extra money. Folding them because "it's only K9s" gives up EV.

## Rule of thumb

- With two or more limpers and an ante, overlimp suited and connected hands, and iso the
  stronger high cards.
- Fold only the hands that are bad whether you see a flop or not (J7o, offsuit gappers).

## The engine's numbers

BTN, two Calling-station limpers, ante 0.5, standard table (EV in bb, against folding):

| Hand | Best | Overlimp | Iso to 5 |
|---|---|---|---|
| K9s | iso to 5 (close) | +0.53 | +0.80 |
| T8s | overlimp (close) | +0.33 | −0.10 |
| A4o | iso to 5 (close) | +0.28 | +1.31 |
| J7o | fold (close) | −0.01 | −0.96 |

## Limits

Close spots: either answer within the band is defensible. The limp EV is a floor.

## Links

None yet. External links are added only after Ian approves each one.
