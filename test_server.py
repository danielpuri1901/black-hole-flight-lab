"""Check the HTTP boundary, including traversal and non-finite inputs."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from serve import ROOT, make_server, parse_flight


class ServerTests(unittest.TestCase):
    def test_live_flight_carries_matching_trace_and_exact_certificate(self):
        from verify_certificate import verify_certificate
        server = make_server(ROOT, 0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            paths = [('/api/showcase', 'capture'),
                     ('/api/flyby?energy=1.1&angular_momentum=3.5&model=small-11', 'capture'),
                     ('/api/flyby?energy=1.1&angular_momentum=5.5&model=large-55', 'escape')]
            for path, outcome in paths:
                with self.subTest(path=path), urlopen(base + path) as response:
                    flight = json.load(response)
                    self.assertEqual(flight['actual'], outcome)
                    self.assertEqual(flight['true_trace']['outcome'], outcome)
                    self.assertEqual(verify_certificate(flight['certificate']), outcome)
                    self.assertEqual(flight['certificate_verified_outcome'], outcome)
                    profile = flight['barrier_profile']
                    self.assertEqual(len(profile['points']), 1200)
                    self.assertEqual(flight['uncertain'], abs(profile['model_margin']) <= flight['uncertainty_margin_threshold'])
                    self.assertEqual(flight['true_trace']['diagnostics']['initial_radial_velocity'],
                                     flight['model_trace']['diagnostics']['initial_radial_velocity'])
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    def test_flight_rejects_nonfinite_out_of_range_and_unknown_models(self):
        valid = 'energy=1.1&angular_momentum=4.5&model=small-11'
        self.assertEqual(parse_flight(valid, {'small-11'}), (1.1, 4.5, 'small-11'))
        for query in [valid.replace('1.1', 'nan'), valid.replace('1.1', 'inf'),
                      valid.replace('1.1', '0.9'), valid.replace('4.5', '99'),
                      valid.replace('small-11', '../secret'), valid + '&energy=1.2']:
            with self.subTest(query=query), self.assertRaises(ValueError):
                parse_flight(query, {'small-11'})

    def test_server_serves_only_public_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'dashboard').mkdir()
            (root / 'results').mkdir()
            (root / 'dashboard/index.html').write_text('<h1>Flight</h1>')
            (root / 'results/summary.json').write_text(json.dumps({'model_files': {}}))
            (root / 'private.txt').write_text('must not be served')
            server = make_server(root, 0)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                with urlopen(base + '/') as response:
                    self.assertIn(b'Flight', response.read())
                with urlopen(base + '/api/summary') as response:
                    self.assertEqual(json.load(response), {'model_files': {}})
                for path in ['/private.txt', '/results/../private.txt',
                             '/results/%2e%2e/private.txt', '/results/']:
                    with self.subTest(path=path), self.assertRaises(HTTPError) as raised:
                        urlopen(base + path)
                    self.assertEqual(raised.exception.code, 404)
                    raised.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                worker.join()


if __name__ == '__main__':
    unittest.main()
