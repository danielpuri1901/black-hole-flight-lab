# Powered flight engine

The engine evolves a powered, equatorial timelike trajectory in Schwarzschild spacetime.
It uses G=c=M=1 and proper time τ.
It does not apply a Newtonian force to a fixed geodesic.

## State and controls

The state is `[r, u, L, φ, q]`, where `u=dr/dτ`, `L=r²dφ/dτ`, and `q` is consumed proper impulse.
Set `f=1−2/r`, `h=√f`, `p=L/r`, and `E=√(u²+f(1+p²))`.
Energy and angular momentum can change during a burn.

The action is a two-component vector in the unit disk.
The engine clips its magnitude and multiplies it by `MAX_ACCEL=0.035`.
The resulting acceleration `a=(a_r,a_φ)` is measured in instantaneous rest axes obtained by a rotationless boost of the static observer's radial and tangential axes.
These axes are defined by that boost at each state; they are not a transported spacecraft attitude.

In the static orthonormal frame, the ship has spatial four-velocity `w=(u/h,p)` and temporal component `γ=E/h`.
The applied four-acceleration is

```
Â⁰ = w·a
Âspatial = a + w(w·a)/(γ+1)
```

This construction gives `U·A=0` and `A·A=|a|²`.
For stable evaluation near the safety surface, define `S=u*a_r+h*p*a_φ`.
The reduced equations are

```
dr/dτ = u
du/dτ = −1/r² + L²/r³ − 3L²/r⁴ + h*a_r + u*S/(E+h)
dL/dτ = r*a_φ + L*S/(E+h)
dφ/dτ = L/r²
dq/dτ = |a|
dE/dτ = S
```

The force construction and rocket mass law follow the covariant bounded-acceleration formulation in [Henriques and Natário, The rocket problem in general relativity](https://arxiv.org/abs/1105.5235).
The background metric and geodesic connection follow [Carroll, Lecture Notes on General Relativity, section 7](https://arxiv.org/abs/gr-qc/9712019).
The algebraic reduction above was derived for this implementation.

## Fuel and mission events

The impulse budget is `Q_MAX=0.7`.
For the stated constant exhaust speed `v_e=0.7c`, the mass ratio is `m/m₀=exp(−q/v_e)`.
The inferred dry mass is `m_dry/m₀=exp(−Q_MAX/v_e)`.
The displayed remaining propellant fraction is `(m−m_dry)/(m₀−m_dry)`.
Fuel exhaustion splits the integration interval at the exact burn time; the remaining interval coasts.
This is an ideal rocket model with constant maximum proper acceleration, not a detailed engine or vehicle model.

The safety surface is `r=2.1`.
Crossing it ends the mission as `safety_cutoff`; it does not prove horizon capture or impossibility of a different future maneuver.
The escape label requires `r≥20`, outward radial motion, and `E≥1+10⁻⁶`.
The intended mission then finishes by coasting.
This numerical rule is not a formal certificate for future arbitrary thrust.
A few floating-point units of interior margin and radial speed `10⁻¹²` make the high-accuracy escape event return a consistent terminal label at a turnaround.

`step()` uses batched RK4 for candidate planning and bisects terminal crossings.
Its intermediate stages use a bounded exterior continuation if a stage crosses the mission surface.
The accepted trajectory stops at the surface; the continuation does not model motion inside it.
`advance()` uses scalar DOP853 for executed flight, locates mission events, and returns actual elapsed proper time through `return_info=True`.
Both functions freeze terminal states.

## Verification

Run `python3 -m unittest -v test_pilot_physics`.
All 11 tests pass.
The reference test constructs Christoffel symbols directly from metric derivatives and integrates `[t,r,φ,Uᵗ,Uʳ,Uφ,q]`.
It does not call the reduced engine's derivative.
It includes three exterior burns and one burn ending at the safety surface.

Measured on the installed local Python, NumPy, and SciPy:

| Check | Observed result |
| --- | --- |
| Three exterior burns versus full coordinate reference | Maximum state error `9.38×10⁻¹³` |
| Safety-ending burn versus full coordinate reference | Maximum state error `3.22×10⁻¹¹`; event-time error `1.55×10⁻¹¹` |
| Full-reference four-velocity normalization | Maximum error `6.81×10⁻¹¹` including safety-ending burn |
| Zero-thrust inward coast through safety event | Energy error `1.12×10⁻¹¹`; angular momentum unchanged |
| Fuel exhaustion at τ=0.37 inside a two-unit interval | State error against independently split reference `1.78×10⁻¹⁵` |
| RK4 errors for 2, 4, 8, 16 substeps | `1.49×10⁻⁶`, `9.59×10⁻⁸`, `6.03×10⁻⁹`, `3.77×10⁻¹⁰` |
| 256 identical candidate states, 60 intervals, four substeps | `0.053 s`; all resulting states finite |

The checks also cover a circular coast, acceleration orthogonality and magnitude, the energy work identity, action limits, broadcasting, empty fuel, terminal freezing, invalid inputs, and the escape-turnaround regression.
An early centrifugal rewrite omitted a factor of radius.
The coast regression reproduced a `0.0461` energy error before that line was corrected.
No training dataset had been generated from that version.

These checks establish numerical agreement on the tested states, not formal correctness over every launch or control sequence.
Planner timesteps still need refinement when candidate decisions depend on small differences near a boundary.
The flight model omits spin, inclination, self-gravity, radiation forces, and vehicle attitude dynamics.
The cockpit's cinematic observer offset and static photon-camera approximation are separate rendering limits.

## Selected-plan refinement

A separate development check used 16 launches from `mission_states(40217,16)`.
Each launch used the existing classical planner with its default 64 random candidates and two search rounds, seeded with `7000+launch_index`.
The selected 12-command plan was held fixed, followed by 48 coast intervals of duration two.
Each rollout used four-substep RK4, eight-substep RK4, and independently scheduled scalar DOP853 execution with `rtol=10⁻¹⁰`.
All 16 selected plans escaped under all three integrations.
The comparison took 9.19 seconds locally.

| Quantity | Four RK4 substeps | Eight RK4 substeps |
| --- | --- | --- |
| Classification disagreements with DOP853 | 0/16 | 0/16 |
| Maximum absolute terminal-state component error | `1.60×10⁻⁵` | `1.01×10⁻⁶` |
| Maximum sampled minimum-radius error | `1.52×10⁻⁶` | `9.70×10⁻⁸` |
| Maximum planner-score error | `2.85×10⁻¹⁴` | `2.85×10⁻¹⁴` |

The score agreement follows from identical fuel expenditure and the same discrete finishing interval for every escaped plan.
It does not mean the continuous trajectories match at machine precision.
The minimum-radius comparison uses interval endpoints, as the current planner score does; it does not measure the exact continuous periapsis.
This check covers selected successful plans, not every rejected candidate or states arbitrarily close to a decision boundary.

The run used Python 3.14.0, NumPy 2.4.2, and SciPy 1.17.1.
Frozen physics SHA256: `fda5353bc2ea5335acc908d2f4e84316180396b34395d80b900eff92c2892d5f`.
Planner SHA256 during the check: `b8be07868c9a88704530a962d80530aa7df77ebf4015f286a20c204da1add6c3`.
Per-case diagnostic output was saved to `/tmp/pilot-plan-refinement.json`.

## Fixed-candidate refinement

Run `python3 verify_pilot_rollouts.py` to reproduce the broader check.
The utility evaluates all 29 fixed burn/coast candidates on the same 16 development launches, for 464 plan rollouts.
It compares four and eight RK4 substeps.
It then checks 64 deterministic plans with DOP853: coast, sustained radial, sustained negative tangential, and mixed burns for each launch.
It also includes any classification disagreements and the surviving candidate with the smallest sampled radius if not already selected.
The recorded run used 65 DOP853 reference plans and took 6.56 seconds.
Its source hashes, seeds, versions, per-case errors, and counts are saved in [physics-validation.json](../results/pilot/physics-validation.json).

There were no four-versus-eight-substep classification disagreements among the 464 candidates.
The 65 adaptive reference plans produced 12 escapes, 44 safety cutoffs, and nine states still flying at the look-ahead limit.
Neither RK4 setting disagreed with those classifications.

| Quantity versus DOP853 | Four RK4 substeps | Eight RK4 substeps |
| --- | --- | --- |
| Classification disagreements | 0/65 | 0/65 |
| Maximum terminal-state component error | `1.23×10⁻³` | `9.78×10⁻⁵` |
| Maximum planner-score error | `5.94×10⁻⁷` | `3.71×10⁻⁸` |
| Maximum sampled minimum-radius error | `1.52×10⁻⁶` | `9.70×10⁻⁸` |

The largest terminal-state error occurs in a coast ending at the safety surface.
Both integrations assign the same cutoff score in that case.
These broader results show that cutoff state components need more refinement than the selected successful plans.
They do not establish an error bound for all candidate launches.
The closest surviving fixed candidate in this set had sampled minimum radius 3.838665M, so the check does not stress survivors arbitrarily close to 2.1M.

The checked controller ranks supplied candidates by physical look-ahead score.
It is not a rigorous safety shield.
If every candidate fails, it can select the highest-scoring failed plan.
The current open-loop burn-then-coast look-ahead also differs from later closed-loop replanning.
