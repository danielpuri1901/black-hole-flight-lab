# Supplemental proposal controls

Two post hoc controls test whether proposal support explains apparent benefits from the learned generator.
They were introduced after inspecting the first three held-out test cases, where the original `random_checked` controller spent its full fuel budget.
The controls change the proposal set, not the dynamics, scoring, integration, feedback loop, or mission launches.
No learned weights or training parameters are changed.
The frozen main benchmark and its results remain separate.
These comparisons are exploratory rather than predeclared confirmatory tests.

`random_with_coast` supplies 16 candidates: one exact coast plan followed by 15 plans from the existing smooth random generator.
It tests the effect of giving random search an explicit zero-thrust option.
`fixed_checked` supplies the existing 29 fixed burn/coast plans.
It tests the hand-designed library without learned proposals or the classical teacher's larger adaptive search.
The candidate counts differ, so this comparison does not isolate equal search cost.

Both controls reuse `flight(..., controller='checked', model=proposal_sampler)`.
The sampler ignores the current context and uses no learned weights.
The existing physical look-ahead score selects a candidate, executes its first command with DOP853, observes the new state, and repeats.
The result is then relabeled with the supplemental controller name.
The random seed remains `91000 + mission index`, as in the main benchmark.
Interventions count selection away from the first coast proposal; they do not mean a learned action was repaired.
Candidate ranking can select a failed plan when all candidates fail.
It is not a rigorous safety shield.

The complete protocol evaluates both controls on all 32 frozen test missions and all 32 frozen stress missions.
This produces 128 flights with at most two local workers.
Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 run_pilot_controls.py --workers 2` after the main benchmark releases the CPUs.
Each flight is an atomic checkpoint under `results/pilot/control-flights/`.
The separate `controls-manifest.json` records source and mission hashes, proposal counts, seed rules, runtime settings, and the post hoc declaration.
The runner refuses to reuse checkpoints with a different manifest.
The final `controls-summary.json` uses the main benchmark's group fields and records individual trials.
Fuel averages include failed missions and must be read alongside escape counts.
Decision times are observed on a shared computer, not an isolated latency benchmark.

## Development smoke check

Run `python3 run_pilot_controls.py --smoke`.
This uses one development launch from seed 40217 and controller seed 71000.
It does not evaluate a held-out launch or create held-out checkpoints.
Both controls escaped in the observed smoke run.
The random control used 49.37% of propellant and reached a sampled minimum radius of 4.562927M.
The fixed library used 41.00% and reached 4.066136M.
These two outcomes validate execution only; they do not estimate general performance.

Sampler checks confirm exact coast at candidate zero, bounded actions, expected shapes, deterministic replay, and independence from input context.
`python3 -m py_compile run_pilot_controls.py` passed.
The complete held-out supplemental run finished with exit code zero.

## Complete held-out results

All 128 flight checkpoints are present.
The current source and mission hashes match the separate manifest.
No flight timed out.
All non-escaping flights ended at the safety surface.
The results are recorded in [controls-summary.json](../results/pilot/controls-summary.json).

| Split | Controller | Escaped | Safety cutoffs | Mean fuel, all flights | Mean fuel, successful flights | Mean decision time |
| --- | --- | --- | --- | --- | --- | --- |
| Test | Random with coast | 29/32 | 3 | 28.68% | 30.53% | 86 ms |
| Test | Fixed checked | 32/32 | 0 | 24.45% | 24.45% | 87 ms |
| Stress | Random with coast | 21/32 | 11 | 23.47% | 34.40% | 88 ms |
| Stress | Fixed checked | 28/32 | 4 | 31.64% | 36.16% | 81 ms |

The Wilson 95% intervals for escape fractions are 75.78% to 96.76% for random with coast on test, 89.28% to 100% for fixed checked on test, 48.31% to 79.59% for random with coast on stress, and 71.93% to 95.03% for fixed checked on stress.
The random control's lower all-flight stress fuel average partly reflects failed missions that chose little or no thrust.
Its successful-only fuel average is therefore also shown.
The timing values come from this separate run on a shared computer and do not establish an isolated speed comparison with the main benchmark.

## Comparison with the frozen main benchmark

The original random checked control escaped on 30/32 test missions and 21/32 stress missions, using mean fuel of 97.20% and 82.10%, respectively.
Replacing one random proposal with exact coast reduced mean fuel to 28.68% and 23.47%.
It rescued no failed mission and changed one test escape into a safety cutoff.
The stress success outcomes stayed the same mission by mission.
This is evidence that explicit proposal support can explain much of the original random baseline's fuel disadvantage.
The change also removes its sixteenth random proposal, so it does not isolate coast support while keeping all original random proposals.

The fixed library matched the classical planner's escape counts: 32/32 test and 28/32 stress.
Their test aggregate fuel and median sampled minimum radius were identical.
They executed identical action sequences on 29 test missions and 25 stress missions.
Their remaining trajectories can differ despite equal escape counts.
The fixed library's mean stress fuel was 31.64%, compared with the classical planner's 31.16%.

The learned checked controller escaped on 32/32 test missions and 23/32 stress missions in the main benchmark.
The fixed library therefore matched its test escape count and exceeded its stress count in these frozen samples.
These controls weaken a claim that learned proposals are needed for the observed task success.
They do not remove the separate result that numerical candidate ranking can improve execution of the fitted generator's raw proposals.
The post hoc timing of these controls, small mission samples, different candidate counts, and shared-machine timing limit broader conclusions.
