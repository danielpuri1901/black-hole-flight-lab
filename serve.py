"""Serve the observatory and its tested numerical flight path on loopback."""
import argparse
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import mimetypes
from pathlib import Path
import threading
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parent


def barrier_profile(energy, momentum, model):
    """Compare potentials after subtracting each world's launch value."""
    import numpy as np
    from physics import potential
    from world_model import analytic_margin
    radii = np.linspace(2.001, 10, 1200)
    exact = potential(radii, momentum) - potential(30, momentum)
    learned = model.potential(radii, momentum) - model.potential(30, momentum)
    return {'points': np.column_stack((radii, exact, learned)).tolist(),
            'launch_radial_energy': float(energy**2 - potential(30, momentum)),
            'exact_margin': float(analytic_margin(energy, momentum)),
            'model_margin': float(model.margin(energy, momentum)),
            'radius_domain': [2.001, 10],
            'definition': 'potential relative to its own launch value'}


def parse_flight(query, model_ids):
    """Reject invalid launches before doing numerical work."""
    values = parse_qs(query, strict_parsing=True)
    if set(values) != {'energy', 'angular_momentum', 'model'} or any(len(v) != 1 for v in values.values()):
        raise ValueError('Supply one energy, angular_momentum, and model.')
    energy = float(values['energy'][0])
    momentum = float(values['angular_momentum'][0])
    model_id = values['model'][0]
    if not math.isfinite(energy) or not 1.002 <= energy <= 1.2:
        raise ValueError('Energy must be between 1.002 and 1.2.')
    if not math.isfinite(momentum) or not 3.5 <= momentum <= 6.3:
        raise ValueError('Angular momentum must be between 3.5 and 6.3.')
    if model_id not in model_ids:
        raise ValueError('Choose a model from the experiment.')
    return energy, momentum, model_id


def parse_pilot(query):
    from pilot_control import CONTROLLERS
    values = parse_qs(query, strict_parsing=True)
    if set(values) != {'radius', 'energy', 'momentum', 'controller'} or any(len(v) != 1 for v in values.values()):
        raise ValueError('Supply one radius, energy, momentum, and controller.')
    numbers = [float(values[name][0]) for name in ('radius', 'energy', 'momentum')]
    for number, bounds in zip(numbers, ((6., 12.), (.995, 1.04), (2.8, 4.2))):
        if not math.isfinite(number) or not bounds[0] <= number <= bounds[1]:
            raise ValueError('Powered launch is outside the supported range.')
    controller = values['controller'][0]
    if controller not in CONTROLLERS:
        raise ValueError('Unknown pilot controller.')
    return (*numbers, controller)


def make_server(root=ROOT, port=8008):
    root = Path(root).resolve()
    computing = threading.BoundedSemaphore(2)

    @lru_cache(maxsize=1)
    def get_pilot():
        from pilot_model import load_model
        return load_model(root / 'results/pilot/model')

    @lru_cache(maxsize=24)
    def powered_flight(radius, energy, momentum, controller):
        from pilot_control import flight
        from pilot_physics import initial_state
        model = get_pilot() if controller in ('learned', 'checked', 'hybrid') else None
        return flight(initial_state(radius, energy, momentum), controller, model, seed=23)

    @lru_cache(maxsize=16)
    def get_model(filename):
        from world_model import load_model
        path = (root / 'results' / filename).resolve()
        if not path.is_relative_to(root / 'results'):
            raise ValueError('Invalid model path.')
        return load_model(path)

    def add_diagnostics(flight, summary, model):
        from verify_certificate import create_certificate, verify_certificate
        profile = barrier_profile(flight['energy'], flight['angular_momentum'], model)
        metric = next(item for item in summary['model_metrics'] if item['model_id'] == flight['model_id'])
        threshold = metric['uncertainty_margin_threshold']
        flight.update(barrier_profile=profile, uncertainty_margin_threshold=threshold,
                      uncertain=abs(profile['model_margin']) <= threshold)
        certificate = create_certificate(flight['energy'], flight['angular_momentum'])
        flight.update(certificate=certificate, certificate_verified_outcome=verify_certificate(certificate))
        return flight

    class Handler(BaseHTTPRequestHandler):
        def reply(self, data, content_type='application/json; charset=utf-8', status=200):
            if not isinstance(data, bytes):
                data = json.dumps(data, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            request = urlsplit(self.path)
            path = unquote(request.path)
            try:
                if path == '/api/summary':
                    self.reply((root / 'results/summary.json').read_bytes())
                    return
                if path == '/api/pilot':
                    launch = parse_pilot(request.query)
                    if not computing.acquire(blocking=False):
                        self.reply({'error': 'Two flights are computing. Try again in a moment.'}, status=503)
                        return
                    try:
                        self.reply(powered_flight(*launch))
                    finally:
                        computing.release()
                    return
                if path == '/api/showcase':
                    flight = json.loads((root / 'results/showcase.json').read_text())
                    summary = json.loads((root / 'results/summary.json').read_text())
                    model = get_model(summary['model_files'][flight['model_id']])
                    self.reply(add_diagnostics(flight, summary, model))
                    return
                if path == '/api/flyby':
                    summary = json.loads((root / 'results/summary.json').read_text())
                    energy, momentum, model_id = parse_flight(request.query, summary['model_files'])
                    if not computing.acquire(blocking=False):
                        self.reply({'error': 'Two flights are computing. Try again in a moment.'}, status=503)
                        return
                    try:
                        from physics import outcome, trace
                        model = get_model(summary['model_files'][model_id])
                        exact = trace(energy, momentum)
                        learned = trace(energy, momentum, potential_fn=model.potential,
                                        derivative_fn=model.derivative)
                        self.reply(add_diagnostics({'energy': energy, 'angular_momentum': momentum,
                                    'model_id': model_id, 'prediction': model.predict_outcome(energy, momentum),
                                    'actual': outcome(energy, momentum),
                                    'true_trace': exact, 'model_trace': learned}, summary, model))
                    finally:
                        computing.release()
                    return
                files = {'/': 'dashboard/index.html', '/index.html': 'dashboard/index.html',
                         '/style.css': 'dashboard/style.css', '/app.js': 'dashboard/app.js',
                         '/cockpit.js': 'dashboard/cockpit.js',
                         '/cockpit-3d.js': 'dashboard/cockpit-3d.js',
                         '/cabin.js': 'dashboard/cabin.js',
                         '/pilot': 'dashboard/pilot.html', '/pilot.js': 'dashboard/pilot.js',
                         '/pilot.css': 'dashboard/pilot.css',
                         '/pilot-article': 'docs/pilot-article.html',
                         '/pilot-article.md': 'docs/pilot-article.md',
                         '/pilot-physics-report.md': 'docs/pilot-physics-report.md',
                         '/pilot-model-report.md': 'docs/pilot-model-report.md',
                         '/pilot-controls-report.md': 'docs/pilot-controls-report.md',
                         '/pilot-cloud-plan.md': 'docs/pilot-cloud-plan.md',
                         '/gyoto-adapter.md': 'docs/gyoto-adapter.md',
                         '/cockpit-frame.png': 'dashboard/cockpit-frame.png',
                         '/black-hole.png': 'dashboard/black-hole.png',
                         '/article': 'docs/article.html', '/article.md': 'docs/article.md'}
                if path in files:
                    filename = root / files[path]
                elif path.startswith('/vendor/') and '..' not in Path(path).parts and '\\' not in path:
                    filename = (root / 'dashboard' / path.lstrip('/')).resolve()
                    if not filename.is_relative_to(root / 'dashboard/vendor'):
                        raise FileNotFoundError()
                elif path.startswith('/results/') and '..' not in Path(path).parts and '\\' not in path:
                    filename = (root / path.lstrip('/')).resolve()
                    if not filename.is_relative_to(root / 'results'):
                        raise FileNotFoundError()
                else:
                    raise FileNotFoundError()
                if not filename.is_file():
                    raise FileNotFoundError()
                content_type = mimetypes.guess_type(filename.name)[0] or 'application/octet-stream'
                self.reply(filename.read_bytes(), content_type)
            except FileNotFoundError:
                self.reply({'error': 'File not available. The experiment may still be running.'}, status=404)
            except (ValueError, OverflowError) as error:
                self.reply({'error': str(error)}, status=400)
            except Exception as error:
                self.log_error('Flight failed: %s', error)
                self.reply({'error': 'Flight calculation failed. Check the server log.'}, status=500)

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8008)
    args = parser.parse_args()
    server = make_server(port=args.port)
    print(f'Black Hole Flight Lab: http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
