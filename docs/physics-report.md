# Physics verification

The physics module passes six direct checks and a 24-flight boundary sweep.
Both numerical tolerance settings agree with the independent polynomial oracle for every flight in the sweep.
The checks use the installed Python 3.14, NumPy, and SciPy.
No package was downloaded.

## Model

The calculation describes inward, equatorial, unpowered, timelike Schwarzschild geodesics in units G=c=M=1.
Proper time is tau, radius is r, energy per unit rest mass is E, and signed angular momentum per unit rest mass is L.
The effective potential is `V(r,L)=(1-2/r)(1+L²/r²)`.
The radial invariant is `v²+V=E²`, where `v=dr/dtau`.
The integrator evolves `dr/dtau=v`, `dv/dtau=-1/r²+L²/r³-3L²/r⁴`, and `dphi/dtau=L/r²`.
SciPy DOP853 uses a maximum step of 2, with adaptive smaller steps and dense interpolation.

Capture stops at r=2.001 on an inward crossing.
This surface is outside the event horizon at r=2.
Escape means an outward return to the initial radius, not a claim about survival or powered flight.
The outward event direction prevents the initial position from being mistaken for escape.
A timeout remains unresolved.
An exact boundary remains unresolved even if numerical roundoff later produces an escape or capture event.

The physical initial velocity is always `-sqrt(E²-V(r0,L))`.
A learned potential uses that same velocity and conserves `K=v0²+Vlearned(r0,L)`.
The returned `energy_drift` is the maximum absolute change in the selected invariant.
The separate `diagnostics.exact_energy_drift` measures change in the exact physical invariant, including during a learned trajectory.
Diagnostics also contain the turning radius, integration steps, stopping surface, terminal time, and initial velocity.
Returned trajectory points include the exact turning event when one exists and the point budget permits it.

Inputs require finite E, L, and r0, with E>=1 and r0>2.
The physics API permits signed L and does not enforce the dashboard's smaller parameter range.
A forbidden initial radius or zero initial radial velocity raises a clear ValueError.
A launch already inside the numerical stopping surface is immediately classified as capture.

## Independent oracle

Multiplying `E²-V` by r³ gives the turning polynomial `P(r)=(E²-1)r³+2r²-L²r+2L²`.
Write delta=E²-1.
Its positive minimum is at `rm=2L²/(sqrt(16+12deltaL²)+4)`.
A minimum at or inside r=2 cannot block the incoming exterior trajectory.
A positive minimum gives capture.
A negative minimum gives escape for an initially allowed launch outside rm, or capture on the inner allowed branch.
A minimum within `64*machine_epsilon*sum(abs(polynomial_terms))` of zero is unresolved.
This oracle does not call the critical-angular-momentum formula.

The separate analytic boundary uses `rc=8/(sqrt((1-3delta)²+16delta)+1-3delta)` and `Lc=rc/sqrt(rc-3)`.
The implementation uses algebraically equivalent expressions at large energies to avoid cancellation.
The array check confirms `Lc/E` approaches sqrt(27) at E=10⁷ and E=10⁸.
At E=1, Lc=4 exactly.

## Commands and results

The first direct test run failed because physics.py did not yet exist.
After implementation, this command passed all six checks:

```sh
python3 -m unittest test_physics.py -v
```

```text
Ran 6 tests in 0.128s
OK
```

The checks cover potential arrays, finite-difference derivatives, both boundary sides, signed angular momentum, the inner allowed branch, invalid launches, terminal surfaces, JSON finiteness, energy drift, tolerance convergence, timeout handling, and identical physical initial velocity in a shifted learned potential.
The large-energy boundary check first failed with an infinite result at E=10⁸ and then passed after the stable expression replaced the cancellation-prone expression.

This command repeats the independent numerical sweep:

```sh
python3 - <<'PY'
import json
import physics

rows = []
for E in [1.0, 1.002, 1.02, 1.1, 1.2, 2.0]:
    critical = float(physics.critical_angular_momentum(E))
    for factor in [0.99, 0.99999, 1.00001, 1.01]:
        L = critical * factor
        loose = physics.trace(E, L, rtol=1e-7, max_points=200)
        tight = physics.trace(E, L, rtol=1e-11, max_points=200)
        assert loose['outcome'] == tight['outcome'] == physics.outcome(E, L)
        rows.append((loose['energy_drift'], tight['energy_drift'],
                     abs(loose['diagnostics']['terminal_time'] - tight['diagnostics']['terminal_time']),
                     abs(loose['points'][-1][2] - tight['points'][-1][2])))
print(json.dumps({'flights': len(rows), 'numerical_oracle_agreements': len(rows),
                  'max_loose_energy_drift': max(row[0] for row in rows),
                  'max_tight_energy_drift': max(row[1] for row in rows),
                  'max_terminal_time_change': max(row[2] for row in rows),
                  'max_final_angle_change': max(row[3] for row in rows)}, indent=2))
PY
```

```json
{
  "flights": 24,
  "numerical_oracle_agreements": 24,
  "max_loose_energy_drift": 1.209201787588654e-06,
  "max_tight_energy_drift": 1.8926549216757849e-10,
  "max_terminal_time_change": 0.0007815301678775199,
  "max_final_angle_change": 0.0008098589862157723
}
```

The final whole-project command was `python3 -m unittest discover -v`.
It passed 11 checks in 0.769 seconds at this checkpoint.
The world-model export test emitted an scikit-learn ConvergenceWarning at its 100-iteration training limit.
The physics checks emitted no warning.
An earlier discovery run failed while serve.py was still being built by another worker; the final run resolved that import failure.

These measurements demonstrate agreement on the sampled cases and convergence as tolerance tightens.
They do not establish an arbitrary numerical error bound at the exact unstable boundary.
