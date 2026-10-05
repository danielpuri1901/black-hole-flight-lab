# Exact rational certificate report

The checker accepts the showcase as capture.
The learned model predicts escape for this flight.
The certificate checks all 4000 frozen flights.
It records 0 disagreements with `physics.outcome` and 0 rejected inputs.
The full counts and any disagreements are in `results/certificates.json`.

## What the checker proves

The inputs are exact rational values of the supplied decimal text.
The generator treats a Python float as `Fraction(str(value))`.
It does not claim that decimal text is the exact binary value held by that float.
The frozen JSON file is read with decimal text preserved.
The reference classifier receives ordinary floats.

The checker reconstructs `P(r) = (E² - 1)r³ + 2r² - L²r + 2L²` from those rational inputs.
It requires `E >= 1`, `P(2) > 0`, and `P(30) > 0`.
The last condition supports a strictly inward launch from `r0 = 30`.
The sign of `L` does not change this radial polynomial.
The checker checks the first polynomial, its exact derivative, every negative remainder identity, and chain termination.
It evaluates every endpoint sign with rational arithmetic.
It counts sign changes after it removes zero signs.
A square-free polynomial has no repeated roots.
For a square-free polynomial, Sturm's theorem gives the number of roots in `(2, 30)`.
Zero roots imply capture under the stated physical assumptions.
Two roots imply escape under those same assumptions.
Other counts remain unresolved.
A nonconstant final divisor means the polynomial has a repeated root.
The checker returns unresolved for every such polynomial, even when that repeated root lies outside `(2, 30)`.
For example, `E = 1, L = 4` is unresolved, as is the conservative case `L = 0`.
The checker handles the quadratic polynomial at `E = 1`.

The physical argument starts with `(dr/dτ)² = E² - (1 - 2/r)(1 + L²/r²) = P(r)/r³`.
The launch uses the negative radial velocity.
If no root lies between the horizon and launch, that inward path has no turning point.
If two simple roots lie there, the outer root is the first inward turning point.
The interval between the roots is forbidden because `P` is negative there.
After turning, the flight returns to radius 30.
For `E >= 1` and `r > 0`, `P''(r) = 6(E² - 1)r + 4 > 0`.
Thus `P'` increases, so `P` has at most one minimum at positive radius.
After the outer root, `P` stays positive and the flight can continue outward.
An exact double root can instead support asymptotic approach, so it does not receive a capture or escape claim.
The physical horizon is radius 2.
The numerical trace stops at radius 2.001.
The certificate proves a horizon classification under the radial reduction, not every detail of that numerical trace.

## Showcase evidence

The rational inputs are `E = 10027667008383363/10000000000000000` and `L = 1608788709625383/400000000000000`.
The exact value `P(30) = 299334665147454162747502933863411/200000000000000000000000000000` is positive.
The signs at radius 2 are `[1, -1, -1, -1]`.
The signs at radius 30 are `[1, 1, 1, -1]`.
The variation counts are 1 and 1.
Their difference is 0.
The entire chain, including exact coefficients, is stored with the showcase.

## Trusted base and limits

No Lean, SymPy, Z3, or other formal prover is imported.
This is a small executable evidence checker, not a Lean-equivalent proof.
Its trusted base includes Python execution, `fractions.Fraction`, the checker code, and Sturm's theorem.
The link from the radial equation to a Schwarzschild geodesic is an external mathematical assumption.
This work does not mechanically prove the Python runtime, Sturm's theorem, general relativity, or the geodesic reduction.
The exact decision does not use floating-point tolerances.
The agreement test compares it with the frozen floating-point classifier and is not an independent proof of that physical reduction.
Agreement on these inputs does not promise agreement at every decimal input.
At `E = 1`, decimal `L` values just below and above 4 give different exact outcomes.
If both decimal values round to the float 4, the float-input certificate remains unresolved.

The whole certificate module has 204 physical lines.
The checker and its arithmetic helpers occupy 102 physical lines, including their docstrings and blank lines.
The other module lines include imports, constants, certificate generation, and JSON loading.
The polynomial degree is at most 3, the chain has at most 4 rows, and each row has at most 4 coefficients.
Input rational text is limited to 128 characters.
Coefficient rational text is limited to 2048 characters.
JSON certificate text is limited to 65536 characters.
The JSON loader rejects duplicate fields and nonfinite constants.
The checker rejects untrimmed polynomials, malformed rational text, false signs, altered endpoints, and unsupported fields.
These bounds limit the accepted evidence format and arithmetic sizes.

## Reproduction

Run `python3 run_certificates.py` to regenerate the evidence and this report.
Run `python3 -m unittest test_certificates` to check valid certificates and adversarial mutations.
The certificate checker uses only the Python standard library.
The comparison runner also uses the existing `physics.py` dependencies.
