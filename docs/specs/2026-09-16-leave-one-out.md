# goblin_fair — leave-one-out attribution

- **Date:** 2026-09-16
- **Author:** Colm Duffy
- **Status:** approved, implemented on `feat/v0.1`
- **Supersedes:** the "Method" decision in `2026-09-15-goblin-fair-v0.1-design.md`

## Why

v0.1 computed `T(SSP + E) − T(SSP)`. The SSP world totals already contain every country,
so for a real emitter (Ireland, the EU, a sector) this counts the emitter twice and
measures "one more Ireland", not Ireland's share of the pathway. Attribution to an
existing emitter is leave-one-out: the world with the emitter minus the world without it.

## Decision

`temperature_contribution(..., method="leave_one_out")` is the default.

| method | "with" run | "without" run | use for |
|---|---|---|---|
| `leave_one_out` | SSP | SSP − E | emitters that are part of the world total |
| `add` | SSP + E | SSP | extra emissions not in the background |

Contribution = `T_with − T_without` per member, for both methods. The unmodified SSP run
(`with` for leave-one-out, `without` for add) is the reference for `background_warming()`,
so background warming is identical for both methods.

## Changes

- `engine.run_pair(..., method)`: scenarios `("with", "without")`. Leave-one-out subtracts
  E from `without`; add adds E to `with`. If the adjusted scenario has negative global CH4
  or N2O emissions in any year, raise `ValueError` naming the species and first year.
  Negative CO2 FFI/AFOLU stays allowed: net-negative CO2 is physically valid.
- `ContributionResult(years, members, with_temperature, without_temperature,
  method="leave_one_out", metadata={})`. `ensemble`, `summary`, `plot` are unchanged
  in meaning. `__repr__` names the method.
- `api`: validates `method` before FaIR runs; `metadata["method"]`.

v0.1 is unreleased, so the field rename is not a breaking release.

## Known property

Because of the non-linearity (CO2 sinks, CH4 lifetime), leave-one-out contributions of
several emitters don't add up exactly to their joint contribution (e.g. EU27 ≠ Σ member
states). Report this with multi-region results.

## Tests

- Fast: invalid `method` fails before FaIR; `ensemble` = with − without;
  `background_warming` uses the SSP run for each method; default method and `repr`.
- Slow: zero emissions give exactly zero contribution for both methods; CO2 pulse timing
  (leave-one-out); background warming identical between methods; leave-one-out ≈ add
  (rtol 2 %) for a small region; CH4 removal larger than the world total raises;
  CO2_AFOLU-only and N2O-only runs warm; an explicit member list keeps its order.
