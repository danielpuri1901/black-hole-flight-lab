"""Independent GYOTO geodesics; compact science JSON on stdout, progress on stderr."""
import argparse
import json
import math
import subprocess
import sys
import time

import numpy as np

import physics

ENERGIES = (1.0, 1.002, 1.02, 1.1, 1.2, 2.0)
MOMENTUM_FACTORS = (0.99, 0.99999, 1.00001, 1.01)
R0 = 30.0
PROPER_TIME_LIMIT = 1000.0


def initial_coord(energy, momentum):
    f = 1.0 - 2.0 / R0
    radial = -math.sqrt(energy**2 - float(physics.potential(R0, momentum)))
    return np.array([0.0, R0, math.pi / 2, 0.0, energy / f, radial, 0.0,
                     momentum / R0**2], dtype=np.float64)


def integrate(energy, momentum, tolerance):
    import gyoto.core
    import gyoto.std

    metric = gyoto.std.KerrBL()
    metric.spin(0.0)
    metric.horizonSecurity(0.0001)
    star = gyoto.std.Star()
    star.metric(metric)
    star.integrator("runge_kutta_fehlberg78")
    star.relTol(tolerance)
    star.absTol(tolerance * 0.01)
    star.deltaMax(0.25)
    star.deltaMaxOverR(0.02)
    star.maxiter(100000)
    star.setInitCoord(initial_coord(energy, momentum), 1)
    # True selects proper time, not Schwarzschild coordinate time.
    star.xFill(PROPER_TIME_LIMIT, True)
    n = star.get_nelements()
    if n < 2:
        raise RuntimeError("GYOTO returned fewer than two states")
    dates, tau = np.empty(n), np.empty(n)
    radius, theta, phi = np.empty(n), np.empty(n), np.empty(n)
    ut, ur, uth, uph = (np.empty(n) for _ in range(4))
    star.get_t(dates)
    try:
        star.get_tau(tau)
    except TypeError:
        # 2.0.2 exposes get_tau(double*) without the newer NumPy wrapper.
        # Keep both the NumPy owner and its C-array view alive through the call.
        tau_view = gyoto.core.array_double.fromnumpy1(tau)
        star.get_tau(tau_view.cast())
    star.getCoord(dates, radius, theta, phi)
    if star.get_nelements() != n:
        raise RuntimeError("GYOTO coordinate retrieval changed stored-state count")
    star.get_dot(ut, ur, uth, uph)
    states = np.column_stack((dates, radius, theta, phi, ut, ur, uth, uph))
    if not np.isfinite(states).all() or not np.isfinite(tau).all():
        raise RuntimeError("GYOTO produced a nonfinite state")
    if np.any(np.diff(tau) <= 0) or np.any(np.diff(dates) <= 0):
        raise RuntimeError("GYOTO times are not strictly increasing")
    capture = np.flatnonzero(radius <= physics.CAPTURE_RADIUS)
    escape = np.flatnonzero((radius >= R0) & (ur > 0) & (tau > 0))
    events = [(int(capture[0]), "capture")] if capture.size else []
    if escape.size:
        events.append((int(escape[0]), "escape"))
    end, label = min(events) if events else (n - 1, "unresolved")
    # Only inspect through the first observed stopping-surface crossing.
    stop = end + 1
    rr, tt, pp = radius[:stop], theta[:stop], phi[:stop]
    f = 1.0 - 2.0 / rr
    measured_energy = f * ut[:stop]
    measured_momentum = rr**2 * np.sin(tt)**2 * uph[:stop]
    norm = (-f * ut[:stop]**2 + ur[:stop]**2 / f + rr**2 * uth[:stop]**2
            + rr**2 * np.sin(tt)**2 * uph[:stop]**2)
    diagnostics = {
        "outcome": label,
        "observed_terminal_tau": float(tau[end]),
        "observed_terminal_radius": float(radius[end]),
        "minimum_radius": float(np.min(rr)),
        "energy_drift": float(np.max(np.abs(measured_energy - energy))),
        "angular_momentum_drift": float(np.max(np.abs(measured_momentum - momentum))),
        "norm_error": float(np.max(np.abs(norm + 1.0))),
        "equatorial_error": float(np.max(np.abs(tt - math.pi / 2))),
        "stored_steps": int(n - 1),
    }
    return diagnostics, (tau[:stop], rr, pp)


def compare_paths(first, second):
    # Interpolation adds error. Report these values as diagnostics, not proof bounds.
    end = min(float(first[0][-1]), float(second[0][-1]))
    sample_times = np.linspace(0.0, end, 200)
    first_r = np.interp(sample_times, first[0], first[1])
    second_r = np.interp(sample_times, second[0], second[1])
    first_phi = np.interp(sample_times, first[0], np.unwrap(first[2]))
    second_phi = np.interp(sample_times, second[0], np.unwrap(second[2]))
    return {"radius_difference": float(np.max(np.abs(first_r - second_r))),
            "azimuth_difference": float(np.max(np.abs(first_phi - second_phi))),
            "shared_proper_time": end}


def package_versions():
    result = subprocess.run(["dpkg-query", "-W", "-f=${Package}=${Version}\\n",
                             "gyoto", "python3-gyoto"], text=True,
                            capture_output=True, timeout=10)
    return result.stdout.strip().splitlines() if result.returncode == 0 else []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true", help="Run one launch with both tolerances")
    args = parser.parse_args()
    import gyoto.core
    import gyoto.std

    gyoto.core.requirePlugin("stdplug")
    started = time.monotonic()
    launches = [(energy, factor) for energy in ENERGIES for factor in MOMENTUM_FACTORS]
    if args.probe:
        launches = launches[:1]
    rows = []
    for energy, factor in launches:
        momentum = float(physics.critical_angular_momentum(energy)) * factor
        print(f"GYOTO E={energy:g}, L/Lcritical={factor:g}", file=sys.stderr, flush=True)
        expected = physics.outcome(energy, momentum)
        coarse, coarse_path = integrate(energy, momentum, 1e-9)
        tight, tight_path = integrate(energy, momentum, 1e-11)
        reference = physics.trace(energy, momentum, rtol=1e-11,
                                  max_time=PROPER_TIME_LIMIT, max_points=10001)
        reference_points = np.asarray(reference["points"])
        reference_path = (reference_points[:, 0], reference_points[:, 1], reference_points[:, 2])
        agreement = (expected != "unresolved" and expected == reference["outcome"]
                     == coarse["outcome"] == tight["outcome"])
        conserved = (tight["energy_drift"] < 1e-6 and tight["angular_momentum_drift"] < 1e-6
                     and tight["norm_error"] < 1e-5 and tight["equatorial_error"] < 1e-8)
        rows.append({"energy": energy, "momentum_factor": factor, "angular_momentum": momentum,
                     "oracle": expected, "local_integrator": reference["outcome"],
                     "coarse": coarse, "tight": tight,
                     "tolerance_comparison": compare_paths(coarse_path, tight_path),
                     "local_path_comparison": compare_paths(reference_path, tight_path),
                     "classification_agreement": agreement, "conserved_quantities_ok": conserved})
    report = {
        "engine": "GYOTO", "packages": package_versions(), "metric": "zero-spin KerrBL",
        "units": "G=c=M=1", "time_parameter": "proper time",
        "integrator": "runge_kutta_fehlberg78", "tolerances": [1e-9, 1e-11],
        "capture_radius": physics.CAPTURE_RADIUS, "escape_radius": R0,
        "proper_time_limit": PROPER_TIME_LIMIT, "trajectory_count": len(rows),
        "classification_agreement_count": sum(row["classification_agreement"] for row in rows),
        "conserved_quantities_ok_count": sum(row["conserved_quantities_ok"] for row in rows),
        "passed": all(row["classification_agreement"] and row["conserved_quantities_ok"] for row in rows),
        "photon_checks": {"performed": False, "reason": "This bounded run checks timelike launches only."},
        "limitations": ["Sampled crossings are not exact event times.",
                        "Path differences include linear interpolation error.",
                        "Independent numerical agreement is not a formal proof."],
        "runtime_seconds": time.monotonic() - started, "flights": rows,
    }
    encoded = json.dumps(report, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode()) >= 100000:
        raise RuntimeError("Scientific JSON exceeds 100,000-byte output limit")
    print(encoded)
    if not report["passed"]:
        print("GYOTO validation has unresolved flights, disagreement, or excessive drift.", file=sys.stderr)


if __name__ == "__main__":
    main()
