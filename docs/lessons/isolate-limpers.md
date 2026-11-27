# Isolate weak limpers

Behind a limper, a raise that takes the pot heads-up with a better hand beats an overlimp. It
pays most against limpers who call too much with weak hands.

## The idea

A limper's range is capped: strong hands usually raise. Raising behind it (an "iso") does
three things:
- it wins the pot at once when the limper folds;
- it plays the hand heads-up and in position when the limper calls;
- it keeps the blinds out.

Overlimping gives all three away, and invites a raise behind you.

## Rule of thumb

- Behind loose limpers (Calling station), iso with good high cards (KJo, A8o and better) for
  value. They call with worse.
- Behind tight limpers (Nit), their limp range is narrow and strong. Iso less; fold the
  hands that only beat their weakest limps.
- Weak suited hands that need a multiway pot (76s, Q9s) usually fold rather than overlimp
  when someone behind raises often.

## The engine's numbers

BTN, one limper, no ante, standard table (EV in bb, against folding):

| Hand | vs Calling-station limper | vs Nit limper |
|---|---|---|
| KJo | iso to 4 +1.13, overlimp −0.03 | fold; iso to 4 −0.02 |
| A8o | iso to 4 +0.86 | iso to 4 +1.03 |
| Q9s | fold; overlimp −0.15, iso −0.44 | fold; overlimp −0.13 |
| 76s | fold; overlimp −0.29 | fold; overlimp −0.28 |

## Limits

The limp EV is a floor: a raise behind your limp counts as a fold
([`sixmax-preflop.md`](../sixmax-preflop.md), "Limping"). Overlimps look a little worse here
than they are.

## Links

None yet. External links are added only after Ian approves each one.
