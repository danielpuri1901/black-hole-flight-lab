"""Bounded rational Sturm certificates for inward Schwarzschild launches.

This executable checker trusts Python/Fraction and Sturm's theorem.
The geodesic reduction and physical interpretation are external assumptions.
Coefficients use ascending powers. No floating arithmetic decides an outcome.
"""

import json
import re
from fractions import Fraction


VERSION = "schwarzschild-sturm-v1"
SEMANTICS = "exact rational values of supplied decimal text; inward launch; G=c=M=1"
MAX_INPUT_TEXT = 128
MAX_COEFFICIENT_TEXT = 2048
_RATIONAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:/[1-9][0-9]*)?\Z")
_DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE]([+-]?[0-9]{1,3}))?\Z")


def _rational(text, limit=MAX_COEFFICIENT_TEXT):
    if not isinstance(text, str) or len(text) > limit or not _RATIONAL.fullmatch(text):
        raise ValueError("expected bounded canonical rational text")
    value = Fraction(text)
    if str(value) != text:
        raise ValueError("rational text is not canonical")
    return value


def _input(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Fraction)):
        raise ValueError("input must be decimal text, int, finite float, or Fraction")
    text = str(value)
    if len(text) > MAX_INPUT_TEXT:
        raise ValueError("input text exceeds certificate bound")
    match = _DECIMAL.fullmatch(text)
    if not _RATIONAL.fullmatch(text) and not match:
        raise ValueError("input is not finite decimal or rational text")
    if match and match.group(1) and abs(int(match.group(1))) > MAX_INPUT_TEXT:
        raise ValueError("decimal exponent exceeds certificate bound")
    return _rational(str(Fraction(text)), MAX_INPUT_TEXT)


def _trim(polynomial):
    polynomial = list(polynomial)
    while len(polynomial) > 1 and polynomial[-1] == 0:
        polynomial.pop()
    return polynomial


def _derivative(polynomial):
    return _trim([i * coefficient for i, coefficient in enumerate(polynomial)][1:])


def _remainder(dividend, divisor):
    remainder = list(dividend)
    while len(remainder) >= len(divisor) and remainder != [0]:
        shift = len(remainder) - len(divisor)
        multiplier = remainder[-1] / divisor[-1]
        for i, coefficient in enumerate(divisor):
            remainder[i + shift] -= multiplier * coefficient
        remainder = _trim(remainder)
    return remainder


def _evaluate(polynomial, point):
    value = Fraction(0)
    for coefficient in reversed(polynomial):
        value = value * point + coefficient
    return value


def _signs(chain, point):
    return [(value > 0) - (value < 0) for value in
            (_evaluate(polynomial, point) for polynomial in chain)]


def _variations(signs):
    nonzero = [sign for sign in signs if sign]
    return sum(left != right for left, right in zip(nonzero, nonzero[1:]))


def _polynomial(E, L):
    if E < 1:
        raise ValueError("energy must be at least 1")
    polynomial = _trim([2 * L * L, -L * L, Fraction(2), E * E - 1])
    if _evaluate(polynomial, 2) <= 0 or _evaluate(polynomial, 30) <= 0:
        raise ValueError("endpoints must be allowed and launch must be strictly inward")
    return polynomial


def _decision(chain, lower, upper):
    square_free = len(chain[-1]) == 1
    root_count = _variations(lower) - _variations(upper) if square_free else None
    outcome = {0: "capture", 2: "escape"}.get(root_count, "unresolved")
    return square_free, root_count, outcome


def create_certificate(E, L):
    """Treat floats as Fraction(str(value)); decimal text avoids prior rounding."""
    E, L = _input(E), _input(L)
    polynomial = _polynomial(E, L)
    chain = [polynomial, _derivative(polynomial)]
    while len(chain[-1]) > 1:
        remainder = _remainder(chain[-2], chain[-1])
        if remainder == [0]:
            break
        chain.append([-coefficient for coefficient in remainder])
    lower, upper = _signs(chain, 2), _signs(chain, 30)
    square_free, root_count, outcome = _decision(chain, lower, upper)
    certificate = {
        "version": VERSION, "semantics": SEMANTICS,
        "inputs": {"E": str(E), "L": str(L), "r0": "30", "horizon": "2"},
        "chain": [[str(coefficient) for coefficient in row] for row in chain],
        "signs": {"lower": lower, "upper": upper},
        "variations": {"lower": _variations(lower), "upper": _variations(upper)},
        "square_free": square_free, "root_count": root_count, "outcome": outcome,
    }
    verify_certificate(certificate)
    return certificate


def _keys(value, expected):
    if not isinstance(value, dict) or len(value) != len(expected) or set(value) != set(expected):
        raise ValueError("certificate has missing or unexpected fields")


def verify_certificate(certificate):
    """Check bounded evidence; return checked outcome or raise ValueError."""
    _keys(certificate, ("version", "semantics", "inputs", "chain", "signs",
                        "variations", "square_free", "root_count", "outcome"))
    if certificate["version"] != VERSION or certificate["semantics"] != SEMANTICS:
        raise ValueError("unsupported certificate semantics")
    inputs = certificate["inputs"]
    _keys(inputs, ("E", "L", "r0", "horizon"))
    if inputs["r0"] != "30" or inputs["horizon"] != "2":
        raise ValueError("certificate endpoints must be 2 and 30")
    E = _rational(inputs["E"], MAX_INPUT_TEXT)
    L = _rational(inputs["L"], MAX_INPUT_TEXT)
    polynomial = _polynomial(E, L)
    encoded_chain = certificate["chain"]
    if not isinstance(encoded_chain, list) or not 2 <= len(encoded_chain) <= 4:
        raise ValueError("Sturm chain must contain 2 to 4 polynomials")
    chain = []
    for row in encoded_chain:
        if not isinstance(row, list) or not 1 <= len(row) <= 4:
            raise ValueError("polynomial degree exceeds certificate bound")
        decoded = [_rational(coefficient) for coefficient in row]
        if decoded == [0] or _trim(decoded) != decoded:
            raise ValueError("zero or untrimmed chain polynomial")
        chain.append(decoded)
    if chain[:2] != [polynomial, _derivative(polynomial)]:
        raise ValueError("chain must start with physical polynomial and its derivative")
    for i in range(2, len(chain)):
        expected = [-value for value in _remainder(chain[i - 2], chain[i - 1])]
        if chain[i] != expected:
            raise ValueError("Sturm negative remainder identity failed")
    if _remainder(chain[-2], chain[-1]) != [0]:
        raise ValueError("Sturm chain is truncated")
    _keys(certificate["signs"], ("lower", "upper"))
    _keys(certificate["variations"], ("lower", "upper"))
    lower, upper = _signs(chain, 2), _signs(chain, 30)
    for endpoint, expected in (("lower", lower), ("upper", upper)):
        supplied = certificate["signs"][endpoint]
        if (not isinstance(supplied, list) or len(supplied) != len(expected)
                or any(type(s) is not int for s in supplied)
                or supplied != expected):
            raise ValueError("endpoint signs do not match exact evaluation")
        variation = certificate["variations"][endpoint]
        if type(variation) is not int or variation != _variations(expected):
            raise ValueError("endpoint variation count is incorrect")
    square_free, root_count, outcome = _decision(chain, lower, upper)
    if type(certificate["square_free"]) is not bool or certificate["square_free"] != square_free:
        raise ValueError("square-free claim is incorrect")
    supplied_count = certificate["root_count"]
    if supplied_count != root_count or (supplied_count is not None and type(supplied_count) is not int):
        raise ValueError("root count is incorrect")
    if certificate["outcome"] != outcome:
        raise ValueError("outcome is not implied by checked evidence")
    return outcome


def loads_certificate(text):
    """Reject nonfinite JSON constants and duplicate object fields."""
    if not isinstance(text, str) or len(text) > 65536:
        raise ValueError("certificate JSON exceeds size bound")

    def reject_constant(value):
        raise ValueError("nonfinite JSON constant: " + value)

    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON field: " + key)
            result[key] = value
        return result

    try:
        certificate = json.loads(text, parse_constant=reject_constant, object_pairs_hook=unique_fields)
    except (RecursionError, json.JSONDecodeError) as error:
        raise ValueError("invalid certificate JSON") from error
    verify_certificate(certificate)
    return certificate
