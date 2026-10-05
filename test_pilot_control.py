"""Exercise a real feedback rescue and the powered HTTP boundary."""
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

import numpy as np

from pilot_control import flight, mission_states
from pilot_physics import Q_MAX
from serve import make_server, parse_pilot


class PilotIntegrationTests(unittest.TestCase):
    def test_rendering_modules_are_served_without_path_escape(self):
        server = make_server(port=0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base + '/vendor/three.module.js') as response:
                self.assertIn(response.headers.get_content_type(),
                              ('text/javascript', 'application/javascript'))
                self.assertIn(b'WebGLRenderer', response.read())
            with urlopen(base + '/vendor/addons/postprocessing/EffectComposer.js') as response:
                self.assertIn(b'EffectComposer', response.read())
            for path in ('/vendor/%2e%2e/pilot.js', '/vendor/../../serve.py',
                         '/vendor/missing.js', '/vendor/%5c..%5cserve.py'):
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + path)
                self.assertEqual(error.exception.code, 404)
                error.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    def test_feedback_rescues_a_coasting_failure_with_finite_fuel(self):
        initial = mission_states(90, 3)[0]
        coast = flight(initial, 'coast', seed=1)
        controlled = flight(initial, 'classical', seed=1)
        self.assertEqual(coast['outcome'], 'safety_cutoff')
        self.assertEqual(controlled['outcome'], 'escaped')
        self.assertGreater(controlled['impulse_used'], 0)
        self.assertLess(controlled['impulse_used'], Q_MAX)
        points = np.asarray(controlled['points'])
        self.assertTrue(np.all(np.diff(points[:, 5]) >= -1e-12))
        self.assertTrue(np.all(np.diff(points[:, 0]) > 0))
        self.assertGreaterEqual(points[-1, 1], 20 - 1e-8)
        self.assertGreater(points[-1, 2], 0)
        self.assertGreaterEqual(points[-1, 6], 1 + 1e-6)
        self.assertEqual(controlled['decision_count'], len(points)-1)

    def test_real_http_coast_and_invalid_launches(self):
        server = make_server(port=0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        base = f'http://127.0.0.1:{server.server_port}'
        query = 'radius=9&energy=1.02&momentum=3.4&controller=coast'
        try:
            with urlopen(base + '/api/pilot?' + query) as response:
                result = json.load(response)
            self.assertEqual(result['controller'], 'coast')
            self.assertEqual(result['outcome'], 'safety_cutoff')
            self.assertEqual(result['impulse_used'], 0)
            for bad in [query.replace('radius=9', 'radius=nan'),
                        query.replace('radius=9', 'radius=2'),
                        query.replace('coast', '../private'), query+'&radius=10']:
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + '/api/pilot?' + bad)
                self.assertEqual(error.exception.code, 400)
                error.exception.close()
            with self.assertRaises(ValueError):
                parse_pilot(query.replace('energy=1.02', 'energy=inf'))
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == '__main__':
    unittest.main()
