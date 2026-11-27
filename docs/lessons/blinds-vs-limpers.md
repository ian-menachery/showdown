# Play the blinds against limpers

In the small blind, completing is cheap and often right. In the big blind, check the weak
hands and raise the strong ones: you close the action, but you're out of position.

## The idea

- **Small blind:** you need only half a big blind more, and the pot already holds the
  limps. Complete with most playable hands. Raise only hands that do well heads-up, because
  you'll be out of position against the callers.
- **Big blind:** checking is free. Raise for value with hands that beat the limpers'
  ranges, since loose limpers call with worse. Weak offsuit hands just check.

## Rule of thumb

- SB with two loose limpers: complete Q8o, KTs and small pairs; raise A9o.
- BB with two loose limpers: check Q8o; raise A9o, KTs and 55. They're ahead of a loose
  limping range and win the dead money.

## The engine's numbers

Two Calling-station limpers, no ante, standard table (EV in bb):

| Hand | SB: complete / raise to 5 | BB: check / raise to 5 |
|---|---|---|
| Q8o | +0.11 / −1.49 (complete, clear) | +0.73 / −0.38 (check, clear) |
| A9o | +0.37 / +1.67 (raise, close) | +1.13 / +3.08 (raise, close) |
| KTs | +0.42 / +0.24 (complete, close) | +1.11 / +1.36 (raise, close) |
| 55 | +0.28 / +0.28 (complete, close) | +1.03 / +1.69 (raise, close) |

## Limits

R is assumed: 0.75 for the raiser out of position. Compare EVs within a spot, not across.

## Links

None yet. External links are added only after Ian approves each one.
