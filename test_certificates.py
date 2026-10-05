"""Evidence checks, malformed evidence, and the frozen flight corpus."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from verify_certificate import create_certificate, loads_certificate, verify_certificate


class CertificateTests(unittest.TestCase):
    def test_capture_escape_and_marginal(self):
        for E, L, expected in ((1, 3, "capture"), (1, 5, "escape"),
                               (1, -5, "escape"), (1, 4, "unresolved"),
                               (1, 0, "unresolved"), (1.1, 4, "capture")):
            with self.subTest(E=E, L=L):
                certificate = create_certificate(E, L)
                self.assertEqual(verify_certificate(certificate), expected)
                self.assertEqual(loads_certificate(json.dumps(certificate)), certificate)
        self.assertEqual(len(create_certificate(1, 3)["chain"][0]), 3)

    def test_mutated_evidence_rejected(self):
        original = create_certificate("1.0027667008383363", "4.0219717740634575")
        mutations = (
            lambda c: c["chain"][0].__setitem__(0, "1"),
            lambda c: c["chain"][1].__setitem__(0, "1"),
            lambda c: c["chain"][2].__setitem__(0, "1"),
            lambda c: c["chain"].pop(),
            lambda c: c["chain"][0].append("0"),
            lambda c: c["signs"]["lower"].__setitem__(0, -1),
            lambda c: c["signs"]["lower"].__setitem__(0, True),
            lambda c: c["variations"].__setitem__("upper", 99),
            lambda c: c.__setitem__("root_count", True),
            lambda c: c.__setitem__("root_count", 2),
            lambda c: c.__setitem__("square_free", False),
            lambda c: c.__setitem__("outcome", "escape"),
            lambda c: c["inputs"].__setitem__("horizon", "2001/1000"),
            lambda c: c["inputs"].__setitem__("r0", "31"),
            lambda c: c["inputs"].__setitem__("E", "2/2"),
            lambda c: c["inputs"].__setitem__("L", float("nan")),
            lambda c: c.__setitem__("extra", "ignored"),
            lambda c: c.__setitem__("chain", [["0"]] * 2),
            lambda c: c.__setitem__("chain", [None, None]),
            lambda c: c["chain"][2].__setitem__(0, "9" * 2049),
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                certificate = deepcopy(original)
                mutation(certificate)
                with self.assertRaises(ValueError):
                    verify_certificate(certificate)

    def test_double_root_cannot_claim_safety(self):
        certificate = create_certificate(1, 4)
        self.assertFalse(certificate["square_free"])
        self.assertIsNone(certificate["root_count"])
        for outcome in ("capture", "escape"):
            forged = deepcopy(certificate)
            forged["outcome"] = outcome
            with self.assertRaises(ValueError):
                verify_certificate(forged)

    def test_decimal_text_resolves_below_float_precision(self):
        below = "3.999999999999999999999999999999"
        above = "4.000000000000000000000000000001"
        self.assertEqual(float(below), float(above))
        self.assertEqual(verify_certificate(create_certificate(1, below)), "capture")
        self.assertEqual(verify_certificate(create_certificate(1, above)), "escape")
        self.assertEqual(verify_certificate(create_certificate(1, float(above))), "unresolved")

    def test_input_and_json_rejections(self):
        for E, L in ((0.9, 3), (1, 100), (True, 3), (float("inf"), 3),
                     (float("nan"), 3), ("1e999", 3), ("1" * 129, 3), ([], 3)):
            with self.subTest(E=E, L=L), self.assertRaises(ValueError):
                create_certificate(E, L)
        for text in ('{"outcome": NaN}', '{"outcome": Infinity}',
                     '{"outcome":"capture","outcome":"escape"}', "[]", "{"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                loads_certificate(text)

    def test_all_frozen_flights(self):
        from physics import outcome

        path = Path(__file__).resolve().parent / "results/test_inputs.json"
        frozen = json.loads(path.read_text(), parse_float=str)
        checked, disagreements = 0, []
        for group in ("nominal", "stress"):
            for index, (E, L) in enumerate(frozen[group]):
                exact = verify_certificate(create_certificate(E, L))
                reference = outcome(float(E), float(L))
                checked += 1
                if exact != reference:
                    disagreements.append((group, index, exact, reference))
        self.assertEqual(checked, 4000)
        self.assertEqual(disagreements, [])


if __name__ == "__main__":
    unittest.main()
