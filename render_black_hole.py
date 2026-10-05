"""Static Schwarzschild null-geodesic render. Run --check or --width 1440."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import argparse
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

CAMERA = 32.0
INCLINATION = np.deg2rad(12.5)


def step(r, v, phi, impact, h):
    """RK4 for r'=v, v'=b²(r-3)/r⁴, phi'=b/r², E=1."""
    def rates(radius, speed):
        radius = np.maximum(radius, 1.5)
        return speed, impact**2 * (radius - 3) / radius**4, impact / radius**2
    a, b, c = rates(r, v)
    d, e, f = rates(r + h*a/2, v + h*b/2)
    g, i, j = rates(r + h*d/2, v + h*e/2)
    k, l, m = rates(r + h*g, v + h*i)
    return (r+h*(a+2*d+2*g+k)/6, v+h*(b+2*e+2*i+l)/6,
            phi+h*(c+2*f+2*j+m)/6)


def trace(impact, tangent_y, spacing=0.0225, record_disk=True):
    """Past-directed spatial rays; disk is opaque at its first crossing."""
    size = len(impact)
    r = np.full(size, CAMERA)
    v = -np.sqrt(np.maximum(0, 1-impact**2*(1-2/CAMERA)/CAMERA**2))
    phi = np.zeros(size)
    hit_r = np.zeros(size)
    hit_phi = np.zeros(size)
    captured = np.zeros(size, dtype=bool)
    active = np.arange(size)
    ey = np.sin(INCLINATION)
    for _ in range(1800):
        if not len(active):
            break
        old_r, old_phi = r[active], phi[active]
        old_y = ey*np.cos(old_phi) + tangent_y[active]*np.sin(old_phi)
        h = np.minimum(0.9, spacing*old_r)
        new_r, new_v, new_phi = step(old_r, v[active], old_phi, impact[active], h)
        r[active], v[active], phi[active] = new_r, new_v, new_phi
        new_y = ey*np.cos(new_phi) + tangent_y[active]*np.sin(new_phi)
        crossed = old_y*new_y < 0
        fraction = np.abs(old_y)/(np.abs(old_y)+np.abs(new_y)+1e-20)
        radius = old_r + fraction*(new_r-old_r)
        disk = crossed & (radius >= 6) & (radius <= 18) & record_disk
        ids = active[disk]
        hit_r[ids] = radius[disk]
        hit_phi[ids] = old_phi[disk]+fraction[disk]*(new_phi[disk]-old_phi[disk])
        capture = new_r <= 2.001
        captured[active[capture]] = True
        done = disk | capture | ((new_r >= 60) & (new_v > 0))
        active = active[~done]
    if len(active):
        raise RuntimeError(f"Unresolved rays: {len(active)}")
    return hit_r, hit_phi, captured


def check():
    threshold = 3*np.sqrt(3)
    impacts = threshold*np.array([.90, .99, .999, 1.001, 1.01, 1.10])
    a = trace(impacts, np.zeros(6), .0225, False)[2]
    b = trace(impacts, np.zeros(6), .01125, False)[2]
    expected = np.array([True, True, True, False, False, False])
    assert np.array_equal(a, expected) and np.array_equal(b, expected)
    # Compare disk radii after halving the step for representative screen rays.
    rng = np.random.default_rng(4)
    sx, sy = rng.uniform(-.55, .55, 2000), rng.uniform(-.34, .34, 2000)
    rho = np.hypot(sx, sy)
    impact = CAMERA*rho/np.sqrt((1+rho*rho)*(1-2/CAMERA))
    ty = sy*np.cos(INCLINATION)/rho
    coarse = trace(impact, ty, .0225)[0]
    fine = trace(impact, ty, .01125)[0]
    both = (coarse > 0) & (fine > 0)
    error = np.abs(coarse[both]-fine[both])
    assert error.max() < .002
    assert np.array_equal(coarse > 0, fine > 0)
    r = np.full(6, CAMERA)
    v = -np.sqrt(1-impacts**2*(1-2/CAMERA)/CAMERA**2)
    phi = np.zeros(6)
    energy_error = 0.0
    active = np.arange(6)
    for _ in range(1800):
        if not len(active):
            break
        r[active], v[active], phi[active] = step(r[active], v[active],
            phi[active], impacts[active], np.minimum(.9, .0225*r[active]))
        invariant = v[active]**2+(1-2/r[active])*impacts[active]**2/r[active]**2
        energy_error = max(energy_error, float(np.abs(invariant-1).max()))
        active = active[(r[active] > 2.001) & (r[active] < 60)]
    assert energy_error < 1e-5
    result = {"critical_impact": float(threshold), "capture_labels": a.tolist(),
              "disk_samples": int(both.sum()), "max_radius_error_M": float(error.max()),
              "median_radius_error_M": float(np.median(error)),
              "disk_hit_disagreements": int(np.count_nonzero((coarse>0)!=(fine>0))),
              "max_null_energy_error": energy_error}
    print(result)
    return result


def render(width=1440, output="dashboard/black-hole.png"):
    started = time.perf_counter()
    height = round(width*5/8)
    # Offset gives the interface a quiet upper-left title area.
    x = ((np.arange(width)+.5)/width-.55)*1.62
    y = (.53-(np.arange(height)+.5)/height)*1.0125
    sx, sy = np.meshgrid(x, y)
    rho = np.hypot(sx, sy).ravel()
    impact = CAMERA*rho/np.sqrt((1+rho*rho)*(1-2/CAMERA))
    tx = sx.ravel()/np.maximum(rho, 1e-20)
    ty = sy.ravel()*np.cos(INCLINATION)/np.maximum(rho, 1e-20)
    tz = -sy.ravel()*np.sin(INCLINATION)/np.maximum(rho, 1e-20)
    radii, phases = np.zeros(len(rho)), np.zeros(len(rho))
    shadow = np.zeros(len(rho), dtype=bool)
    # ponytail: fixed camera asset; batches cap memory, no live rendering engine.
    for start in range(0, len(rho), 24000):
        end = min(start+24000, len(rho))
        radii[start:end], phases[start:end], shadow[start:end] = trace(
            impact[start:end], ty[start:end])
    found = radii > 0
    disk = np.zeros((len(rho), 3))
    r, phase = radii[found], phases[found]
    azimuth = np.arctan2(tx[found]*np.sin(phase),
        np.cos(INCLINATION)*np.cos(phase)+tz[found]*np.sin(phase))
    angular_momentum = impact[found]*np.cos(INCLINATION)*tx[found]
    redshift = np.sqrt(1-3/r)/(np.sqrt(1-2/CAMERA)*(1+angular_momentum/r**1.5))
    # Artistic emissivity and colors. Geometry and frequency shift come from GR.
    inner = np.clip((r-6)/1.7, 0, 1)**.65
    outer = np.clip((18-r)/2.0, 0, 1)**1.4
    emission = (9/r)**2.3 * inner*outer
    bands = .86+.09*np.sin(16*r+3*np.sin(azimuth))+.05*np.sin(43*r-9*azimuth)
    spirals = .84+.10*np.sin(7*azimuth+9*np.log(r))+.06*np.sin(13*azimuth+5*r)
    intensity = 2.2*emission*bands*spirals*redshift**3
    heat = np.clip((15-r)/9 + .18*(redshift-1), 0, 1)
    copper = np.array([1.0, .34, .10])
    ivory = np.array([1.0, .86, .64])
    disk[found] = intensity[:, None]*(copper+(ivory-copper)*heat[:, None])
    disk = disk.reshape(height, width, 3)
    # Bloom is a photographic display effect, not additional geodesic emission.
    glow = gaussian_filter(disk, sigma=(width/280, width/280, 0))*.24
    glow += gaussian_filter(disk, sigma=(width/80, width/80, 0))*.15
    rng = np.random.default_rng(12)
    yy, xx = np.mgrid[0:height, 0:width]
    vignette = np.clip(1-((xx/width-.55)**2+(yy/height-.53)**2), .3, 1)
    background = np.empty_like(disk)
    background[:] = [.0032, .0021, .007]
    background *= vignette[..., None]
    # Sparse display stars; positions do not represent a ray-traced star catalogue.
    for _ in range(width//5):
        px, py = rng.integers(width), rng.integers(height)
        if shadow.reshape(height, width)[py, px] or disk[py, px].max()>.05:
            continue
        background[py, px] += rng.uniform(.01, .09)*np.array([.75, .8, 1])
    background[shadow.reshape(height, width)] *= .05
    light = disk+glow+background
    # Film-like compression keeps the hottest approaching side ivory.
    mapped = (1-np.exp(-light))**(1/2.2)
    grain = rng.normal(0, .0013, (height, width, 1))
    pixels = np.uint8(np.clip(mapped+grain, 0, 1)*255)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(pixels).save(output)
    elapsed = time.perf_counter()-started
    print(f"Saved {output}: {width}x{height}, {elapsed:.2f}s, {found.sum()} disk rays")
    return elapsed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--output", default="dashboard/black-hole.png")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check()
    else:
        render(args.width, args.output)
