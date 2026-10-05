"""Check exact certificates against the frozen floating-point reference."""

import ast
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path

import physics
from verify_certificate import create_certificate, verify_certificate


ROOT = Path(__file__).resolve().parent


def main():
    inputs_path = ROOT / "results/test_inputs.json"
    frozen = json.loads(inputs_path.read_text(), parse_float=str)
    showcase_path = ROOT / "results/showcase.json"
    showcase = json.loads(showcase_path.read_text(), parse_float=str)
    certificate = create_certificate(showcase["energy"], showcase["angular_momentum"])
    groups, disagreements, rejected = {}, [], []
    for group in ("nominal", "stress"):
        exact_counts, reference_counts = Counter(), Counter()
        for index, (E, L) in enumerate(frozen[group]):
            reference = physics.outcome(float(E), float(L))
            reference_counts[reference] += 1
            try:
                exact = verify_certificate(create_certificate(E, L))
            except ValueError as error:
                rejected.append({"group": group, "index": index, "E": E, "L": L,
                                 "reason": str(error), "reference": reference})
                continue
            exact_counts[exact] += 1
            if exact != reference:
                disagreements.append({"group": group, "index": index, "E": E, "L": L,
                                      "certificate": exact, "reference": reference})
        groups[group] = {"flights": len(frozen[group]), "checked": sum(exact_counts.values()),
                         "exact_outcomes": dict(exact_counts),
                         "reference_outcomes": dict(reference_counts)}
    kernel_path = ROOT / "verify_certificate.py"
    kernel = kernel_path.read_text()
    checker_functions = {"_rational", "_trim", "_derivative", "_remainder", "_evaluate",
                         "_signs", "_variations", "_polynomial", "_decision", "_keys",
                         "verify_certificate"}
    function_lines = sum(node.end_lineno - node.lineno + 1 for node in ast.parse(kernel).body
                         if isinstance(node, ast.FunctionDef) and node.name in checker_functions)
    result = {
        "method": "bounded exact rational Sturm certificate, not an imported formal prover",
        "input_semantics": "JSON decimal text converted to Fraction; reference receives float",
        "dataset_sha256": hashlib.sha256(inputs_path.read_bytes()).hexdigest(),
        "kernel_sha256": hashlib.sha256(kernel_path.read_bytes()).hexdigest(),
        "kernel_module_physical_lines": len(kernel.splitlines()),
        "checker_function_physical_lines": function_lines,
        "groups": groups, "total_checked": sum(g["checked"] for g in groups.values()),
        "disagreements": disagreements, "rejected_inputs": rejected,
        "showcase": {"certificate": certificate,
                     "checked_outcome": verify_certificate(certificate),
                     "reference_outcome": showcase["actual"],
                     "learned_outcome": showcase["prediction"]},
    }
    (ROOT / "results/certificates.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    P30 = sum(Fraction(c) * 30**i for i, c in enumerate(certificate["chain"][0]))
    report = f"""# Exact rational certificate report

The checker accepts the showcase as {certificate['outcome']}.
The learned model predicts {showcase['prediction']} for this flight.
The certificate checks all {result['total_checked']} frozen flights.
It records {len(disagreements)} disagreements with `physics.outcome` and {len(rejected)} rejected inputs.
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

The rational inputs are `E = {certificate['inputs']['E']}` and `L = {certificate['inputs']['L']}`.
The exact value `P(30) = {P30}` is positive.
The signs at radius 2 are `{certificate['signs']['lower']}`.
The signs at radius 30 are `{certificate['signs']['upper']}`.
The variation counts are {certificate['variations']['lower']} and {certificate['variations']['upper']}.
Their difference is {certificate['root_count']}.
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

The whole certificate module has {result['kernel_module_physical_lines']} physical lines.
The checker and its arithmetic helpers occupy {function_lines} physical lines, including their docstrings and blank lines.
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
"""
    (ROOT / "docs/certificates-report.md").write_text(report)
    print(json.dumps({"total_checked": result["total_checked"], "groups": groups,
                      "disagreements": len(disagreements), "rejected": len(rejected),
                      "showcase": certificate["outcome"]}, indent=2))


if __name__ == "__main__":
    main()
