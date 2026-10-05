# Independent physics engine options

Checked on 2026-10-04.

## Decision

Use GYOTO to check the existing spacecraft trajectories and light rays independently.
Keep the existing dashboard and learned-model experiment.
Installation needs approval because the engine and several dependencies are absent.

## Evidence

- GYOTO is established research software from Observatoire de Paris.
  Its manual documents timelike geodesics for massive particles and null geodesics for photons in Kerr spacetime.
  Zero Kerr spin gives the Schwarzschild case used here.
  The manual includes image generation, published uses, and integrator comparisons.
  [Official manual](https://gyoto.obspm.fr/GyotoManual.pdf).
- GYOTO has current maintenance activity.
  GitHub's API returned an October 2, 2026 commit that adds metric checks.
  The installation guide states that Python 3.9 through 3.14 have been tested.
  It supports MacPorts installation and warns about Clang floating-point behavior.
  These facts support trying GYOTO, but do not verify this M2 machine.
  [Verified commit](https://github.com/gyoto/Gyoto/commit/508b58657a1e465db4647a1397c1a8e36adb4b8b), [installation guide](https://github.com/gyoto/Gyoto/blob/master/INSTALL.Gyoto.md).
- EinsteinPy is an established Python research library with weaker recent maintenance evidence.
  It supplies geodesic calculations and plots, rather than the camera renderer this project needs.
  PyPI lists version 0.4.0, published May 5, 2021.
  Its wheel is 88,123 bytes, excluding dependencies.
  GitHub's API returned May 18, 2024 as the latest main-branch commit.
  Its README names Python 3.7 and 3.8 testing.
  Python 3.14 compatibility remains unverified.
  [Published package](https://pypi.org/project/einsteinpy/), [repository](https://github.com/einsteinpy/einsteinpy).
- Einstein Toolkit is an established numerical-relativity research platform for evolving spacetime, including black-hole mergers.
  Its official download page lists a July 2026 release and C, C++, Fortran, and MPI requirements.
  This project uses fixed Schwarzschild spacetime, so the toolkit adds setup without answering a missing question.
  Scientific visualization requires separate post-processing.
  [Official requirements](https://einsteintoolkit.org/download.html).

## Design

- Use GYOTO; keep EinsteinPy as a possible small trajectory check and exclude Einstein Toolkit from this scope.
- Use GYOTO's Star interface for timelike paths and its photon interface for selected camera rays.
- Compare physical coordinates and conserved quantities before comparing displayed images.
- Export small project-owned measurement files and keep the dashboard independent of engine installation.
- A second implementation checks coding errors; it does not turn the exact capture certificate into a spacecraft-survival proof.

## Proposed installation manifest

Use the documented MacPorts route to keep compiler and C++ libraries within one supported package system.
This adds another package manager because only Homebrew is installed here.
It also adds separate MacPorts Python, rather than modifying the existing framework Python.
The MacPorts installer can change shell PATH settings.
Use explicit interpreter paths for the dashboard and engine adapter.
[Official installer behavior](https://www.macports.org/install.php).

| Item | Purpose | Scope |
| --- | --- | --- |
| MacPorts installer for macOS 26 on Apple Silicon | Supported GYOTO package manager | System install; administrator approval |
| Gyoto | C++ engine and command-line renderer | MacPorts prefix /opt/local |
| py314-gyoto | Python 3.14 interface | Separate MacPorts Python |
| Eigen, LORENE, pkgconfig | Published port build requirements | MacPorts dependencies |
| Boost, CFITSIO, FLINT, UDUNITS2, Xerces-C | Integration and output requirements | MacPorts dependencies |
| Doxygen, SWIG, Python 3.14, NumPy, setuptools, build, pip | Python interface requirements | MacPorts dependencies |
| Compiler and transitive packages | Package resolver requirements | Review resolved list before engine installation |

The observed MacPorts recipe pins source commit 25968c285d78393b3bf91494b0f89f9f75453dff.
It labels the package 2.0.2-20251105, revision 1.
Its source archive is exactly 2,346,138 bytes.
The full compiler and dependency transfer has no verified total here.
Allow roughly 0.5 to 2 GiB transfer and 2 to 6 GiB disk as planning estimates, not measured requirements.
Stop and revise the manifest if the resolved installation exceeds those limits.
Do not enable MPI or add visualization apps for the first check.
[Authoritative package recipe](https://github.com/macports/macports-ports/blob/master/science/Gyoto/Portfile).

No software downloads, installations, cloud resources, or engine executions occurred during this comparison.
The exact transitive package list remains unresolved.

## Validation after approval

1. Run a supplied GYOTO example and relevant engine tests.
   Record versions, output, memory use, and runtime.
   Fail if installation or engine tests fail.
2. Translate the existing launch into a normalized four-velocity at r=30, with G=c=M=1 and equatorial motion.
   Set u^t=E/(1-2/r), u^phi=L/r^2, and the existing negative radial velocity.
   Check normalization and conserved energy before integration.
   Convert velocities if the interface requires derivatives with respect to coordinate time.
3. Repeat existing energies with angular momentum factors 0.99, 0.99999, 1.00001, and 1.01 around the capture boundary.
   Require identical resolved capture labels at the same stopping surfaces.
   Compare radius and azimuth at shared proper times.
   Tighten both integrators and inspect convergence.
   Keep exact boundary cases unresolved.
4. Compare selected photons using the same local camera frame and disk geometry.
   Require matching capture and disk-hit labels away from boundaries.
   Check intersection coordinates and frequency shifts under tighter integration.
   Compare images only after these checks, with matched emission laws and artistic effects removed.

## Unknowns

- MacPorts binaries and required variants remain unverified on this macOS 26.5 arm64 machine.
- Installation size and build memory remain estimates; performance on 8 GiB needs measurement.
- The adapter and matched engine stopping settings still need implementation after installation approval.

Confidence is high that GYOTO matches the physics.
Installation and runtime confidence remains moderate until the engine runs.

## Current machine check

Python reports version 3.14.0.
Named executable checks found no GYOTO, GeodesicViewer, EinsteinPy, or MacPorts command.
Named application checks found no matching app in /Applications or ~/Applications.
Current Python finds neither gyoto nor einsteinpy.
NumPy, SciPy, Matplotlib, and Numba are available; Astropy and SymPy are absent.
Homebrew reports Boost 1.90.0 installed.
Other named GYOTO dependencies were absent from its installed-package query.
